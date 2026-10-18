"""``pyflic --help`` lists every subcommand and every installed entry point."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pyflic.__main__ as cli

ROOT = Path(__file__).resolve().parents[1]


def _entry_points() -> list[str]:
    with open(ROOT / "pyproject.toml", "rb") as handle:
        return list(tomllib.load(handle)["project"]["scripts"])


def test_help_lists_every_entry_point_in_pyproject(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pyflic", "--help"])
    cli.main()
    printed = capsys.readouterr().out
    for name in _entry_points():
        assert f"    {name} " in printed, name
    assert "pyflic-types" in printed


def test_help_lists_every_subcommand(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pyflic", "-h"])
    cli.main()
    printed = capsys.readouterr().out
    for command in cli._COMMANDS:
        assert f"    pyflic {command}" in printed, command
