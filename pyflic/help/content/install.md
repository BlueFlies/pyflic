# Installing pyflic

## Requirements

- **Python 3.13 or later**
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip

Everything else — PyQt6, matplotlib, pandas, numpy, statsmodels, plotnine — is installed
automatically as a dependency.

## From GitHub

The usual way to install.

```bash
uv add git+https://github.com/PletcherLab/pyflic.git
```

To pin a version, which is what you want once an analysis is underway, name its release
tag in place of `<version>`, for example the version `pyflic version` prints:

```bash
uv add git+https://github.com/PletcherLab/pyflic.git@v<version>
```

Into a standalone environment, or with pip:

```bash
uv pip install git+https://github.com/PletcherLab/pyflic.git
pip install git+https://github.com/PletcherLab/pyflic.git
```

## From a wheel file

If you were sent a `.whl`, use its file name, which carries its version:

```bash
uv add pyflic-<version>-py3-none-any.whl
uv pip install pyflic-<version>-py3-none-any.whl
pip install pyflic-<version>-py3-none-any.whl
```

## Checking it worked

```bash
pyflic version
```

Then open the help you are reading now:

```bash
pyflic help
```

Both working means the package and its GUI dependencies are installed correctly.

## Commands

| Command | What it does |
|---|---|
| `pyflic` | Analysis Hub — the same as `pyflic hub` |
| `pyflic hub [folder]` | Analysis Hub, opened on a Batch, a Project or an Experiment Directory |
| `pyflic config [folder]` | Config Editor, on the folder's `flic_config.yaml` (or a YAML file you name; default: the current folder's, else an empty editor) |
| `pyflic qc [experiment]` | QC Viewer on an Experiment Directory (default: the current folder) |
| `pyflic plots [project]` | Plot Editor, on a Project's publication figures |
| `pyflic help [topic]` | This help window |
| `pyflic lint <folder>` | Validate every `flic_config.yaml` under the folder, and report old layouts |
| `pyflic report <folder>` | Write the PDF report of a Project or an Experiment Directory |
| `pyflic batch <folder> [script]` | Run the designated Project Script in every Project under the folder |
| `pyflic clear-cache <experiment>` | Remove an Experiment Directory's cached feeding summaries |
| `pyflic version` | Print the installed version |
| `pyflic-types [type]` | Experiment Type Editor, on the shipped types and your lab's library (optionally opened on one type) |

`pyflic --help` prints the command list as text. The Experiment Type Editor has no
`pyflic` subcommand: run `pyflic-types`, or open it from the Hub's Tools panel
(**Experiment type editor**).

## Updating

```bash
uv add --upgrade git+https://github.com/PletcherLab/pyflic.git
pip install --upgrade --force-reinstall git+https://github.com/PletcherLab/pyflic.git
```

Pin a version for work in progress. Detection parameters and their defaults can change
between releases, and re-analysing half of an experiment on a different version is a
reproducibility problem that is very hard to notice afterwards. Record the output of
`pyflic version` alongside your results.

## Version control for your data

pyflic writes results beside your data. If you keep experiments in git, exclude the
generated folders:

```gitignore
analysis/
qc/
figures/
.pyflic_cache/
```

Keep `flic_config.yaml`, `project.yaml`, `batch.yaml`, `experiment_type.yaml`,
`plot_specs.yaml` and `remove_chambers.csv` under version control — together they define the
analysis, and they are small.

---

Next: **[Getting started](getting-started.md)**
