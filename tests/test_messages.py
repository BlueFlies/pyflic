"""PyMCU's ``Messages.csv`` (docs/v4-data-plan.md, stream 6).

Two writers: PyMCU from 10/17/2026 quotes a message holding a comma and folds
repeats into one line; earlier builds left every line unquoted, so the message
text can hold commas. ``Millisecond`` is an
unformatted float and ``Sample`` is the record ``Index``.  The reader splits
off the first five fields and the last one and keeps the rest as the
message; a missing file is an empty frame.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from pyflic.base import messages

from v4_fixtures import family_specs, fixed_ratio_spec, messages_text, simulate, write_v4_recording

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


def test_a_quoted_message_keeps_its_commas_and_loses_its_quotes():
    """PyMCU from 10/17/2026 writes Messages.csv with the csv module."""
    frame = messages.parse(HEADER + '1,10/17/2026,10:02:13,200.0,1234,'
                           '"Lost 33 records (6.6 s): Index 1201 to 1233, from 10:02:13.",Error\n'
                           '2,10/17/2026,10:02:14,0.0,9,"He said ""hi"", twice",Notice\n')
    assert frame["Message"].tolist() == [
        "Lost 33 records (6.6 s): Index 1201 to 1233, from 10:02:13.", 'He said "hi", twice']
    assert frame["MsgType"].tolist() == ["Error", "Notice"]
    assert frame["Index"].tolist() == [1234, 9]


def test_folded_repeats_are_counted():
    """A message that came again within 10 minutes is one line ending
    "(repeated N more times, the last at HH:MM:SS)"."""
    frame = messages.parse(HEADER
                           + "1,10/17/2026,10:05:00,0.0,1500,DFM 1 error: No Ack "
                             "(repeated 41 more times, the last at 10:14:59),Notice\n"
                           + "1,10/17/2026,10:20:00,0.0,6000,DFM 1 error: No Ack "
                             "(repeated 1 more time, the last at 10:20:01),Notice\n"
                           + "0,10/17/2026,10:30:00,0.0,0,Recording ended,Unknown\n")
    assert frame["Repeats"].tolist() == [41, 1, 0]
    assert frame["Message"].iloc[0].endswith("(repeated 41 more times, the last at 10:14:59)")
    assert messages.count(frame) == 45 and messages.count(messages.empty()) == 0


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
    ## PyMCU's wording from 10/17/2026, quoted for its comma.
    assert errors["Message"].iloc[0].startswith("Lost 4 records (0.8 s): Index 501 to 504, from ")
    ## A DFM's view keeps its own rows and the MCU's.
    mine = messages.for_dfm(frame, 2)
    assert mine["DFM"].tolist() == [0, 2, 2, 0]
    assert messages.errors(mine)["Index"].tolist() == [803, 1204]
    assert messages_text(spec, index_gaps=gaps).count("\n") == len(frame) + 1


def test_record_messages_find_lost_records_and_restarts():
    """Both writers' lost-records wording and PyMCU's two restart errors;
    every other message is left out."""
    frame = messages.parse(
        HEADER
        + "0,10/17/2026,10:00:00,0.0,0,Recording started,Unknown\n"
        + '1,10/17/2026,10:02:13,200.0,1234,"Lost 33 records (6.6 s): Index 1201 to 1233, from 10:02:13.",Error\n'
        + '1,10/17/2026,10:03:00,0.0,1501,"Lost 1 record (0.2 s): Index 1500, from 10:03:00.",Error\n'
        + "2,10/17/2026,10:04:00,0.0,40,Lost 5 records (1.0 s): 30 to 34 (counted from the DFM's restart), "
          "from 10:04:00.,Error\n"
        + "1,10/17/2026,10:05:00,0.0,2021,(2021) Skipped index: (2000) ,Error\n"
        + "1,10/17/2026,10:06:00,0.0,2022,(2022) Skipped index: (2021) ,Error\n"
        + "1,10/17/2026,10:07:00,0.0,1,DFM 1 restarted: its record count went back from 3000 to 1. Its Paradigm "
          "state and Activation counts started again. Sending its Interval and linkage again.,Error\n"
        + "1,10/17/2026,10:07:00,0.0,3000,DFM 1 recorded nothing for about 5 s while it restarted: Index 3001 to "
          "3025 are missing.,Error\n"
        + "1,10/17/2026,10:08:00,0.0,3100,DFM 1 error: No Ack (repeated 3 more times, the last at 10:08:03),Notice\n")
    found = messages.record_messages(frame)
    assert list(found.columns) == list(messages.RECORD_MESSAGE_COLUMNS)
    assert found["Kind"].tolist() == [messages.LOST_RECORDS] * 4 + [messages.DFM_RESTARTED, messages.RESTART_GAP]
    assert found["DFM"].tolist() == [1, 1, 2, 1, 1, 1]
    assert found["First"].tolist() == [1201, 1500, pd.NA, 2001, pd.NA, 3001]
    assert found["Last"].tolist() == [1233, 1500, pd.NA, 2020, pd.NA, 3025]
    assert found["Records"].tolist() == [33, 1, 5, 20, pd.NA, 25]
    assert found["Time"].iloc[0] == pd.Timestamp(datetime(2026, 10, 17, 10, 2, 13, 200000))
    empty = messages.record_messages(messages.empty())
    assert empty.empty and list(empty.columns) == list(messages.RECORD_MESSAGE_COLUMNS)


def test_the_simulators_restart_messages_are_found(tmp_path):
    spec = family_specs(minutes=6.0)["restart"]
    write_v4_recording(tmp_path, spec, index_gaps={1: [(1200, 7)]})
    found = messages.record_messages(messages.read(tmp_path))
    assert found[["DFM", "Kind", "First", "Last", "Records"]].values.tolist() == [
        [2, messages.DFM_RESTARTED, pd.NA, pd.NA, pd.NA],
        [2, messages.RESTART_GAP, 631, 645, 15],
        [1, messages.DFM_RESTARTED, pd.NA, pd.NA, pd.NA],
        [1, messages.RESTART_GAP, 901, 925, 25],
        [1, messages.LOST_RECORDS, 1201, 1207, 7],
    ]


def test_describe_names_the_source_and_the_record():
    frame = messages.parse(HEADER + "0,10/16/2026,23:34:00,0.0,0,Recording started,Unknown\n"
                           "2,10/16/2026,23:37:24,200.0,1021,(1021) Skipped index: (1000),Error\n")
    assert messages.describe(frame.iloc[0]) == "10/16/2026 23:34:00.000  MCU: Recording started"
    assert messages.describe(frame.iloc[1]) == \
        "10/16/2026 23:37:24.200  DFM 2, Index 1021: (1021) Skipped index: (1000)"
