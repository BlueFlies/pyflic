"""PyMCU's ``Messages.csv``: what the MCU logged while it recorded.

PyMCU writes the file beside the DFM data: a header
``DFM,Date,Time,Millisecond,Sample,Message,MsgType`` and one line per message.
``Millisecond`` is an unformatted float (``200.0``), ``Sample`` holds the DFM's
record ``Index`` the message refers to (0 for the MCU's own messages), and
``MsgType`` is ``Error``, ``Notice``, ``Warning`` or ``Unknown``.  An empty log
is the single line ``No messages``.  Messages from DFM 0 are the MCU's own
("Recording started"), not a DFM's.

Two writers exist, and both are read:

* PyMCU 4.0.0 from 10/17/2026 (``MessagesList``, with the csv module) quotes a
  message holding a comma, and writes a message that came again within 10
  minutes once, ending "(repeated N more times, the last at HH:MM:SS)".
  :func:`parse` keeps that text and puts N in ``Repeats``.
* Earlier builds (``GetMessageStringForFile``) wrote every line **unquoted**,
  so a message's own commas made extra fields: the line is split on its first
  five commas and its last one, and whatever lies between is the message.

:func:`read` turns the file into a frame the integrity report and the QC
Viewer list; a missing file is an empty frame, never an error.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

MESSAGES_FILENAME = "Messages.csv"
#: The columns :func:`read` returns.  ``Repeats`` is how many more times the
#: message came, folded into this line by PyMCU (0 for a message that came once).
MESSAGE_COLUMNS: tuple[str, ...] = ("DFM", "Time", "Index", "Message", "MsgType", "Repeats")
#: ``MsgType`` of the messages the integrity report lists.
MSG_ERROR = "Error"
#: The ``DFM`` of the MCU's own messages.
MCU_ID = 0

_HEAD_FIELDS = 5            # DFM, Date, Time, Millisecond, Sample
#: The ending PyMCU gives a message it folded repeats into (``Message.Text``).
_REPEATED = re.compile(r"\(repeated (\d+) more times?, the last at [0-9:]+\)\s*$")
_TIME_FORMATS = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S")


def find_messages(data_dir: str | Path) -> Path | None:
    """``Messages.csv`` in *data_dir* (name matched case-insensitively, as
    the Opto Program is found), or ``None``."""
    try:
        entries = sorted(Path(data_dir).iterdir())
    except OSError:
        return None
    return next((p for p in entries
                 if p.is_file() and p.name.lower() == MESSAGES_FILENAME.lower()), None)


def empty() -> pd.DataFrame:
    """A frame with :data:`MESSAGE_COLUMNS` and no rows."""
    return pd.DataFrame({
        "DFM": pd.array([], dtype="Int64"), "Time": pd.Series([], dtype="datetime64[ns]"),
        "Index": pd.array([], dtype="Int64"), "Message": pd.Series([], dtype=object),
        "MsgType": pd.Series([], dtype=object), "Repeats": pd.array([], dtype="Int64")})


def _integer(text: str) -> int | None:
    try:
        return int(float(text.strip()))
    except ValueError:
        return None


def _time(date: str, clock: str, millisecond: str) -> datetime | None:
    stamp = f"{date.strip()} {clock.strip()}"
    for fmt in _TIME_FORMATS:
        try:
            when = datetime.strptime(stamp, fmt)
            break
        except ValueError:
            continue
    else:
        return None
    try:
        return when + timedelta(milliseconds=float(millisecond))
    except ValueError:
        return when


def parse(text: str) -> pd.DataFrame:
    """The messages in *text*, the contents of a ``Messages.csv``.

    Reads both writers (see the module docstring): a quoted message keeps
    its commas and loses its quotes, and an unquoted one is rebuilt from the
    fields between the first five and the last.  Tolerant: blank lines, the
    header (wherever it appears), ``No messages`` and lines with fewer than
    seven fields are skipped; a field that does not parse is missing rather
    than an error.
    """
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        fields = next(csv.reader([line]))
        if len(fields) < _HEAD_FIELDS + 2 or fields[0].strip().upper() == "DFM":
            continue
        dfm, date, clock, millisecond, sample = fields[:_HEAD_FIELDS]
        message = ",".join(fields[_HEAD_FIELDS:-1]).strip()
        repeated = _REPEATED.search(message)
        rows.append({
            "DFM": _integer(dfm), "Time": _time(date, clock, millisecond),
            "Index": _integer(sample),
            "Message": message,
            "MsgType": fields[-1].strip(),
            "Repeats": int(repeated.group(1)) if repeated else 0,
        })
    if not rows:
        return empty()
    frame = pd.DataFrame(rows, columns=list(MESSAGE_COLUMNS))
    frame["DFM"] = pd.array(frame["DFM"].tolist(), dtype="Int64")
    frame["Index"] = pd.array(frame["Index"].tolist(), dtype="Int64")
    frame["Repeats"] = pd.array(frame["Repeats"].tolist(), dtype="Int64")
    frame["Time"] = pd.to_datetime(frame["Time"])
    return frame


def count(frame: pd.DataFrame) -> int:
    """How many messages *frame* stands for: each line once, plus the
    repeats PyMCU folded into it."""
    if frame.empty:
        return 0
    return int(len(frame) + frame["Repeats"].fillna(0).astype(int).sum())


def read(data_dir: str | Path) -> pd.DataFrame:
    """``Messages.csv`` of the recording in *data_dir*, as a frame with
    columns ``DFM, Time, Index, Message, MsgType`` (:func:`parse`); an empty
    frame when there is no such file."""
    path = find_messages(data_dir)
    if path is None:
        return empty()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    except OSError:
        return empty()
    return parse(text)


def for_dfm(frame: pd.DataFrame, dfm_id: int) -> pd.DataFrame:
    """The messages of DFM *dfm_id* and the MCU's own (DFM 0), in file order."""
    if frame.empty:
        return frame
    ids = frame["DFM"].astype("Int64")
    keep = (ids == int(dfm_id)) | (ids == MCU_ID)
    return frame[keep.fillna(False).to_numpy(dtype=bool)].reset_index(drop=True)


def errors(frame: pd.DataFrame) -> pd.DataFrame:
    """The rows of *frame* whose ``MsgType`` is ``Error``."""
    if frame.empty:
        return frame
    keep = frame["MsgType"].astype(str).str.strip().str.lower() == MSG_ERROR.lower()
    return frame[keep.to_numpy(dtype=bool)].reset_index(drop=True)


def describe(row) -> str:
    """One message as a line of text: time, source, record and message."""
    when = row["Time"]
    stamp = when.strftime("%m/%d/%Y %H:%M:%S.%f")[:-3] if pd.notna(when) else "(no time)"
    dfm = row["DFM"]
    source = "MCU" if pd.notna(dfm) and int(dfm) == MCU_ID else (
        f"DFM {int(dfm)}" if pd.notna(dfm) else "DFM ?")
    index = row["Index"]
    record = f", Index {int(index)}" if pd.notna(index) and int(index) > 0 else ""
    return f"{stamp}  {source}{record}: {row['Message']}"
