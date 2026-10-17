"""PyMCU's ``Messages.csv`` (docs/v4-data-plan.md, stream 6).

The file is unquoted: the message text can hold commas, ``Millisecond`` is an
unformatted float and ``Sample`` is the record ``Index``.  The reader splits
off the first five fields and the last one and keeps the rest as the
message; a missing file is an empty frame.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from pyflic.base import messages

from v4_fixtures import fixed_ratio_spec, messages_text, simulate, write_v4_recording

HEADER = "DFM,Date,Time,Millisecond,Sample,Message,MsgType\n"


def test_a_message_with_commas_keeps_them():
    text = (HEADER
            + "0,10/16/2026,23:34:00,0.0,0,Recording started,Unknown\n"
            + "3,10/16/2026,23:37:24,200.0,1021,Skipped index, then resumed, at (1021),Error\n")
    frame = messages.parse(text)
    assert list(frame.columns) == list(messages.MESSAGE_COLUMNS)
    assert len(frame) == 2
    row = frame.iloc[1]
    assert row["Message"] == "Skipped index, then resumed, at (1021)"
    assert row["MsgType"] == "Error"
    assert row["DFM"] == 3 and row["Index"] == 1021
    assert row["Time"] == pd.Timestamp(datetime(2026, 10, 16, 23, 37, 24, 200000))


def test_the_unformatted_millisecond_is_read_as_a_float():
    frame = messages.parse(HEADER + "1,01/02/2026,08:00:01,123.456,7,hello,Notice\n")
    assert frame["Time"].iloc[0] == pd.Timestamp(datetime(2026, 1, 2, 8, 0, 1, 123456))


def test_a_missing_file_is_an_empty_frame(tmp_path):
    frame = messages.read(tmp_path)
    assert frame.empty and list(frame.columns) == list(messages.MESSAGE_COLUMNS)


def test_an_empty_log_and_junk_lines_are_skipped(tmp_path):
    (tmp_path / "Messages.csv").write_text("No messages\n", encoding="utf-8")
    assert messages.read(tmp_path).empty
    frame = messages.parse(HEADER + "\n garbage\n" + HEADER
                           + "x,bad date,bad,ms,s,still read,Warning\n")
    assert len(frame) == 1
    row = frame.iloc[0]
    assert pd.isna(row["DFM"]) and pd.isna(row["Time"]) and pd.isna(row["Index"])
    assert row["Message"] == "still read" and row["MsgType"] == "Warning"


def test_the_file_name_is_matched_case_insensitively(tmp_path):
    (tmp_path / "messages.CSV").write_text(HEADER + "0,10/16/2026,23:34:00,0.0,0,Hi,Unknown\n",
                                           encoding="utf-8")
    assert messages.read(tmp_path)["Message"].tolist() == ["Hi"]


def test_the_simulators_messages_read_back(tmp_path):
    spec = fixed_ratio_spec(minutes=6.0, dfm_ids=(1, 2))
    gaps = {1: [(500, 4)], 2: [(800, 2), (1200, 3)]}
    write_v4_recording(tmp_path, spec, index_gaps=gaps, results=simulate(spec))
    frame = messages.read(tmp_path)
    assert frame["DFM"].tolist() == [0, 1, 2, 2, 0]
    assert frame["Message"].iloc[0] == "Recording started"
    ## PyMCU logs a gap on the first record after it.
    errors = messages.errors(frame)
    assert errors["Index"].tolist() == [505, 803, 1204]
    assert errors["Message"].iloc[0] == "(505) Skipped index: (500)"
    ## A DFM's view keeps its own rows and the MCU's.
    mine = messages.for_dfm(frame, 2)
    assert mine["DFM"].tolist() == [0, 2, 2, 0]
    assert messages.errors(mine)["Index"].tolist() == [803, 1204]
    assert messages_text(spec, index_gaps=gaps).count("\n") == len(frame) + 1


def test_describe_names_the_source_and_the_record():
    frame = messages.parse(HEADER + "0,10/16/2026,23:34:00,0.0,0,Recording started,Unknown\n"
                           "2,10/16/2026,23:37:24,200.0,1021,(1021) Skipped index: (1000),Error\n")
    assert messages.describe(frame.iloc[0]) == "10/16/2026 23:34:00.000  MCU: Recording started"
    assert messages.describe(frame.iloc[1]) == \
        "10/16/2026 23:37:24.200  DFM 2, Index 1021: (1021) Skipped index: (1000)"
