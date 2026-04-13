"""
FLIC Analysis Hub
=================
PyQt6 launcher for common pyflic analysis workflows. Opens the config editor and
QC viewer in separate processes. Runs analysis in a background thread.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import traceback
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def _read_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _chamber_size_from_cfg(cfg: dict[str, Any]) -> int | None:
    g = cfg.get("global")
    if isinstance(g, dict):
        params = g.get("params") or g.get("parameters")
        if isinstance(params, dict) and params.get("chamber_size") is not None:
            return int(params["chamber_size"])
    dfms = cfg.get("dfms") or cfg.get("DFMs")
    nodes: list[Any]
    if isinstance(dfms, dict):
        nodes = list(dfms.values())
    elif isinstance(dfms, list):
        nodes = dfms
    else:
        nodes = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        p = node.get("params") or node.get("parameters")
        if isinstance(p, dict) and p.get("chamber_size") is not None:
            return int(p["chamber_size"])
    return None


def _norm_et(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    return s or None


def read_project_meta(project_dir: Path) -> dict[str, Any]:
    """Lightweight parse of ``flic_config.yaml`` for status display (no DFM load)."""
    cfg_path = project_dir / "flic_config.yaml"
    if not cfg_path.is_file():
        return {"ok": False, "error": f"No flic_config.yaml in {project_dir}"}
    try:
        cfg = _read_yaml(cfg_path)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Could not read config: {e}"}
    g = cfg.get("global")
    et = _norm_et(g.get("experiment_type") if isinstance(g, dict) else None)
    cs = _chamber_size_from_cfg(cfg)
    inferred = et
    if inferred is None and cs == 1:
        inferred = "single_well"
    elif inferred is None and cs == 2:
        inferred = "two_well"
    return {
        "ok": True,
        "experiment_type": et,
        "inferred_type": inferred,
        "chamber_size": cs,
        "config_path": cfg_path,
    }


def _resolve_cli(name: str, module: str) -> list[str]:
    exe = shutil.which(name)
    if exe:
        return [exe]
    return [sys.executable, "-m", module]


class _SignalWriter:
    """File-like object that emits a Qt signal on each line written."""

    def __init__(self, signal: pyqtSignal) -> None:
        self._signal = signal
        self._buf = ""

    def write(self, text: str) -> int:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._signal.emit(line)
        return len(text)

    def flush(self) -> None:
        if self._buf:
            self._signal.emit(self._buf)
            self._buf = ""


class AnalysisWorker(QObject):
    """Runs a callable in a worker thread; streams stdout/stderr to the log."""

    log = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, task: Callable[[], None]) -> None:
        super().__init__()
        self._task = task

    def run(self) -> None:
        import matplotlib

        matplotlib.use("Agg")
        writer = _SignalWriter(self.log)
        try:
            from contextlib import redirect_stderr, redirect_stdout

            with redirect_stdout(writer), redirect_stderr(writer):
                self._task()
            writer.flush()
        except Exception as e:  # noqa: BLE001
            writer.flush()
            self.failed.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        finally:
            self.finished.emit()


class AnalysisHubWindow(QMainWindow):
    def __init__(self, project_dir: str | Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("pyflic — Analysis Hub")
        self.resize(920, 720)
        self._initial_dir = Path(project_dir).expanduser().resolve() if project_dir else None

        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None
        self._busy = False
        self._cached_exp: Any = None
        self._cached_exp_key: tuple | None = None

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)

        # Project row
        proj_row = QHBoxLayout()
        proj_row.addWidget(QLabel("Project directory:"))
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select a folder containing flic_config.yaml and data/")
        proj_row.addWidget(self._path_edit, stretch=1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_project)
        proj_row.addWidget(browse)
        outer.addLayout(proj_row)

        self._status = QLabel("No project loaded.")
        self._status.setWordWrap(True)
        outer.addWidget(self._status)

        # Options
        opt_box = QGroupBox("Load options")
        opt_form = QFormLayout(opt_box)
        self._spin_start = QDoubleSpinBox()
        self._spin_start.setRange(0, 1_000_000)
        self._spin_start.setSpecialValueText("0")
        self._spin_start.setValue(0)
        opt_form.addRow("Start minute (0 = from beginning):", self._spin_start)

        self._spin_end = QDoubleSpinBox()
        self._spin_end.setRange(0, 1_000_000)
        self._spin_end.setSpecialValueText("0")
        self._spin_end.setValue(0)
        opt_form.addRow("End minute (0 = through end of recording):", self._spin_end)

        self._chk_parallel = QCheckBox("Load DFMs in parallel")
        self._chk_parallel.setChecked(True)
        opt_form.addRow(self._chk_parallel)
        outer.addWidget(opt_box)

        # Toolbar actions
        tool = QHBoxLayout()
        self._btn_config = QPushButton("Edit config (pyflic-config)…")
        self._btn_config.clicked.connect(self._launch_config_editor)
        tool.addWidget(self._btn_config)

        self._btn_qc = QPushButton("QC viewer (pyflic-qc)…")
        self._btn_qc.clicked.connect(self._launch_qc_viewer)
        tool.addWidget(self._btn_qc)

        self._btn_refresh = QPushButton("Refresh project info")
        self._btn_refresh.clicked.connect(self._refresh_meta)
        tool.addWidget(self._btn_refresh)

        tool.addStretch()
        outer.addLayout(tool)

        # Tabs — built once; conditional tabs are added/removed in _refresh_meta
        self._tabs = QTabWidget()
        self._tab_overview = self._build_tab_overview()
        self._tab_grouped = self._build_tab_grouped()
        self._tab_two_well = self._build_tab_two_well()
        self._tab_hedonic = self._build_tab_hedonic()
        self._tab_pr = self._build_tab_pr()
        outer.addWidget(self._tabs, stretch=1)

        # Log
        outer.addWidget(QLabel("Output"))
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(5000)
        outer.addWidget(self._log, stretch=1)

        self._path_edit.editingFinished.connect(self._refresh_meta)

        start_dir = self._initial_dir or Path.cwd()
        self._path_edit.setText(str(start_dir))
        self._refresh_meta()

        self._analysis_buttons: list[QPushButton] = []
        for w in self.findChildren(QPushButton):
            t = w.text()
            if t.startswith("Browse") or t in (
                "Edit config (pyflic-config)…",
                "QC viewer (pyflic-qc)…",
                "Refresh project info",
            ):
                continue
            self._analysis_buttons.append(w)

    def _append_log(self, text: str) -> None:
        self._log.appendPlainText(text.rstrip())

    def _range_minutes(self) -> tuple[float, float]:
        a = float(self._spin_start.value())
        b = float(self._spin_end.value())
        return a, b

    def _project_dir(self) -> Path:
        return Path(self._path_edit.text().strip()).expanduser().resolve()

    def _browse_project(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select project directory", str(self._project_dir()))
        if d:
            self._path_edit.setText(d)
            self._refresh_meta()

    def _refresh_meta(self) -> None:
        self._invalidate_exp_cache()
        p = self._project_dir()
        meta = read_project_meta(p)
        if not meta.get("ok"):
            self._status.setText(meta.get("error", "Invalid project."))
            self._rebuild_tabs(None, None)
            return
        et = meta.get("experiment_type")
        inf = meta.get("inferred_type")
        cs = meta.get("chamber_size")
        parts = [f"<b>{p}</b>"]
        if et:
            parts.append(f"experiment_type: <code>{et}</code>")
        elif inf:
            parts.append(f"experiment_type: <i>unspecified</i> (loads as <code>{inf}</code>)")
        else:
            parts.append("experiment_type: <i>unknown</i>")
        if cs is not None:
            parts.append(f"chamber_size: <code>{cs}</code>")
        data_ok = (p / "data").is_dir()
        parts.append("data/: " + ("found" if data_ok else "<span style='color:#a50'>missing</span>"))
        self._status.setText(" — ".join(parts))
        self._rebuild_tabs(et or inf, cs)

    def _rebuild_tabs(self, exp_type: str | None, chamber_size: int | None) -> None:
        """Show only the analysis tabs appropriate for the experiment type."""
        prev = self._tabs.currentWidget()
        self._tabs.clear()

        # Always shown
        self._tabs.addTab(self._tab_overview, "Overview & QC")
        self._tabs.addTab(self._tab_grouped, "Grouped summaries")

        # Two-well tab: shown when chamber_size is 2 or experiment type implies it
        two_well_types = {"two_well", "hedonic"}
        if chamber_size == 2 or exp_type in two_well_types:
            self._tabs.addTab(self._tab_two_well, "Two-well / choice")

        # Hedonic tab
        if exp_type == "hedonic":
            self._tabs.addTab(self._tab_hedonic, "Hedonic")

        # Progressive ratio tab
        if exp_type == "progressive_ratio":
            self._tabs.addTab(self._tab_pr, "Progressive ratio")

        # Restore previous tab selection if it's still visible
        idx = self._tabs.indexOf(prev)
        if idx >= 0:
            self._tabs.setCurrentIndex(idx)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for w in self._analysis_buttons:
            w.setEnabled(not busy)

    def _clear_worker_refs(self) -> None:
        """Reset references so we don't touch deleted C++ objects on the next run."""
        self._thread = None
        self._worker = None

    def _start_worker(self, task: Callable[[], None]) -> None:
        if self._busy:
            QMessageBox.information(self, "Busy", "An analysis task is already running.")
            return
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, "Busy", "An analysis task is already running.")
            return
        p = self._project_dir()
        if not (p / "flic_config.yaml").is_file():
            QMessageBox.warning(self, "No config", "Select a directory containing flic_config.yaml.")
            return

        self._thread = QThread()
        self._worker = AnalysisWorker(task)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker_refs)
        self._worker.log.connect(self._append_log)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(lambda: self._set_busy(False))

        self._set_busy(True)
        self._thread.start()

    def _on_failed(self, msg: str) -> None:
        self._append_log(msg)
        QMessageBox.critical(self, "Analysis error", msg[:1200])

    def _exp_cache_key(self) -> tuple:
        return (str(self._project_dir()), self._range_minutes(), self._chk_parallel.isChecked())

    def _load_exp(self):
        key = self._exp_cache_key()
        if self._cached_exp is not None and self._cached_exp_key == key:
            print("Using cached experiment (same project / options).", flush=True)
            return self._cached_exp

        from pyflic import load_experiment_yaml

        exp = load_experiment_yaml(
            self._project_dir(),
            range_minutes=self._range_minutes(),
            parallel=self._chk_parallel.isChecked(),
        )
        self._cached_exp = exp
        self._cached_exp_key = key
        return exp

    def _invalidate_exp_cache(self) -> None:
        self._cached_exp = None
        self._cached_exp_key = None

    def _launch_config_editor(self) -> None:
        p = self._project_dir()
        if not p.is_dir():
            QMessageBox.warning(self, "Invalid path", "Choose a valid project directory.")
            return
        cmd = _resolve_cli("pyflic-config", "pyflic.base.config_editor")
        try:
            subprocess.Popen(cmd, cwd=str(p))  # noqa: S603
        except OSError as e:
            QMessageBox.critical(self, "Could not start", str(e))

    def _qc_dir_for_range(self) -> Path:
        """Return the range-specific qc directory, falling back to plain qc/."""
        p = self._project_dir()
        a, b = self._range_minutes()
        if a == 0.0 and b == 0.0:
            return p / "qc"
        ranged = p / f"qc_{int(a)}_{int(b)}"
        if ranged.is_dir():
            return ranged
        return p / "qc"

    def _launch_qc_viewer(self) -> None:
        p = self._project_dir()
        if not p.is_dir():
            QMessageBox.warning(self, "Invalid path", "Choose a valid project directory.")
            return
        qc_dir = self._qc_dir_for_range()
        cmd = _resolve_cli("pyflic-qc", "pyflic.base.qc_viewer")
        cmd = [*cmd, str(p), str(qc_dir)]
        try:
            subprocess.Popen(cmd)  # noqa: S603
        except OSError as e:
            QMessageBox.critical(self, "Could not start", str(e))

    # --- tabs ---

    def _build_tab_overview(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        intro = QLabel(
            "Load experiment summary text, write QC reports only, or run the full basic analysis "
            "(QC → summary → feeding CSV → feeding plot). Matches <code>execute_basic_analysis()</code>."
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(intro)

        b1 = QPushButton("Print experiment summary to log")
        b1.clicked.connect(self._action_summary_text)
        lay.addWidget(b1)

        b2 = QPushButton("Write QC reports only (no summary/plots)")
        b2.clicked.connect(self._action_qc_only)
        lay.addWidget(b2)

        b3 = QPushButton("Run full basic analysis")
        b3.clicked.connect(self._action_basic_full)
        lay.addWidget(b3)
        lay.addStretch()
        return w

    def _build_tab_grouped(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(
            QLabel(
                "Feeding summaries and binned time courses. "
                "Bin size applies to binned CSV and binned licks plot."
            )
        )
        row = QHBoxLayout()
        row.addWidget(QLabel("Bin size (minutes):"))
        self._spin_binsize = QSpinBox()
        self._spin_binsize.setRange(1, 10_000)
        self._spin_binsize.setValue(30)
        row.addWidget(self._spin_binsize)
        row.addStretch()
        lay.addLayout(row)

        b1 = QPushButton("Write feeding summary CSV")
        b1.clicked.connect(self._action_write_feeding_csv)
        lay.addWidget(b1)

        b2 = QPushButton("Write feeding summary plot")
        b2.clicked.connect(self._action_feeding_plot)
        lay.addWidget(b2)

        b3 = QPushButton("Write binned feeding summary CSV")
        b3.clicked.connect(self._action_binned_csv)
        lay.addWidget(b3)

        b4 = QPushButton("Plot binned licks by treatment (mean ± SEM)")
        b4.clicked.connect(self._action_binned_plot)
        lay.addWidget(b4)

        lay.addStretch()
        return w

    def _build_tab_two_well(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        note = QLabel(
            "For two-well experiments (<code>chamber_size: 2</code>): "
            "facet jitter plot of well durations by treatment."
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(note)
        b = QPushButton("Save facet well-duration plot (plotnine)")
        b.clicked.connect(self._action_facet_durations)
        lay.addWidget(b)
        lay.addStretch()
        return w

    def _build_tab_hedonic(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        note = QLabel(
            "Requires <code>experiment_type: hedonic</code>. Runs hedonic basic analysis "
            "(standard pipeline plus hedonic feeding plot and weighted duration summary)."
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(note)
        b = QPushButton("Run hedonic execute_basic_analysis()")
        b.clicked.connect(self._action_hedonic_full)
        lay.addWidget(b)
        lay.addStretch()
        return w

    def _build_tab_pr(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        note = QLabel(
            "Requires <code>experiment_type: progressive_ratio</code>. "
            "Breaking-point schedule layout from R port (configurations 1–4)."
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(note)
        row = QHBoxLayout()
        row.addWidget(QLabel("Breaking-point configuration:"))
        self._spin_pr_cfg = QSpinBox()
        self._spin_pr_cfg.setRange(1, 4)
        self._spin_pr_cfg.setValue(1)
        row.addWidget(self._spin_pr_cfg)
        row.addStretch()
        lay.addLayout(row)

        b = QPushButton("Save breaking-point plots (plotnine, all DFMs)")
        b.clicked.connect(self._action_pr_plots)
        lay.addWidget(b)
        lay.addStretch()
        return w

    # --- actions ---

    def _action_summary_text(self) -> None:
        def task() -> None:
            exp = self._load_exp()
            print(exp.summary_text(), flush=True)

        self._start_worker(task)

    def _action_qc_only(self) -> None:
        def task() -> None:
            exp = self._load_exp()
            out = exp.write_qc_reports()
            print(f"QC written to: {out}", flush=True)

        self._start_worker(task)

    def _action_basic_full(self) -> None:
        rm = self._range_minutes()

        def task() -> None:
            exp = self._load_exp()
            paths = exp.execute_basic_analysis(range_minutes=rm)
            for k, v in paths.items():
                print(f"{k}: {v}", flush=True)

        self._start_worker(task)

    def _action_write_feeding_csv(self) -> None:
        rm = self._range_minutes()

        def task() -> None:
            exp = self._load_exp()
            p = exp.write_feeding_summary(range_minutes=rm)
            print(f"Wrote: {p}", flush=True)

        self._start_worker(task)

    def _action_feeding_plot(self) -> None:
        rm = self._range_minutes()

        def task() -> None:
            exp = self._load_exp()
            p = exp.write_feeding_summary_plot(range_minutes=rm)
            print(f"Wrote: {p}", flush=True)

        self._start_worker(task)

    def _action_binned_csv(self) -> None:
        rm = self._range_minutes()
        bs = float(self._spin_binsize.value())

        def task() -> None:
            exp = self._load_exp()
            p = exp.binned_feeding_summary(binsize_min=bs, range_minutes=rm, save=True)
            print(f"Binned rows: {len(p)}", flush=True)

        self._start_worker(task)

    def _action_binned_plot(self) -> None:
        rm = self._range_minutes()
        bs = float(self._spin_binsize.value())

        def task() -> None:
            exp = self._load_exp()
            fig = exp.plot_binned_licks_by_treatment(
                binsize_min=bs,
                range_minutes=rm,
            )
            out = exp.analysis_dir / "binned_licks_by_treatment.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(str(out), dpi=150, bbox_inches="tight")
            print(f"Wrote: {out}", flush=True)

        self._start_worker(task)

    def _action_facet_durations(self) -> None:
        rm = self._range_minutes()

        def task() -> None:
            from pyflic import TwoWellExperiment

            exp = self._load_exp()
            if not isinstance(exp, TwoWellExperiment):
                raise TypeError(
                    "This action requires a two-well experiment (chamber_size: 2). "
                    f"Got {type(exp).__name__}."
                )
            p = exp.facet_plot_well_durations(range_minutes=rm)
            out = exp.analysis_dir / "facet_well_durations.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            p.save(str(out), dpi=150)
            print(f"Wrote: {out}", flush=True)

        self._start_worker(task)

    def _action_hedonic_full(self) -> None:
        rm = self._range_minutes()

        def task() -> None:
            from pyflic import HedonicFeedingExperiment
            from pyflic.base.experiment import Experiment

            exp = self._load_exp()
            if not isinstance(exp, HedonicFeedingExperiment):
                raise TypeError(
                    "Set experiment_type: hedonic in flic_config.yaml. "
                    f"Got {type(exp).__name__}."
                )
            Experiment.execute_basic_analysis(
                exp,
                range_minutes=rm,
            )
            exp.hedonic_feeding_plot(save=True, range_minutes=rm)
            exp.weighted_duration_summary(save=True, range_minutes=rm)
            print("Hedonic basic analysis complete.", flush=True)

        self._start_worker(task)

    def _action_pr_plots(self) -> None:
        cfg = int(self._spin_pr_cfg.value())

        def task() -> None:
            from pyflic import ProgressiveRatioExperiment

            exp = self._load_exp()
            if not isinstance(exp, ProgressiveRatioExperiment):
                raise TypeError(
                    "Set experiment_type: progressive_ratio in flic_config.yaml. "
                    f"Got {type(exp).__name__}."
                )
            ad = exp.analysis_dir
            if ad is None:
                raise ValueError("No project_dir on experiment.")
            ad.mkdir(parents=True, exist_ok=True)
            for dfm_id, dfm in sorted(exp.dfms.items()):
                p9 = exp.plot_breaking_point_dfm_gg(dfm, cfg)
                out = ad / f"breaking_point_dfm{dfm_id}_config{cfg}.png"
                p9.save(str(out), dpi=150)
                print(f"Wrote: {out}", flush=True)

        self._start_worker(task)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("pyflic Analysis Hub")
    project_dir = sys.argv[1] if len(sys.argv) > 1 else None
    win = AnalysisHubWindow(project_dir=project_dir)
    win.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
