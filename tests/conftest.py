"""Every test runs against a throwaway pyflic settings folder.

The apps save preferences to ``~/.config/pyflic/ui.json``: the theme a
toggle chooses, the help window's geometry, the lab's type library folder.
A test that toggles a theme or closes the help window would otherwise
rewrite the user's own file (a theme-toggle test once left a developer's
pyflic in light mode).  The type library's default folder lives there too,
so isolating it also keeps a lab's real types out of the tests' type lists.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path_factory, monkeypatch):
    folder = tmp_path_factory.mktemp("config")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(folder))
    monkeypatch.delenv("PYFLIC_TYPE_LIBRARY", raising=False)
    ## ui.settings fixes its path at import, so the variable alone is not enough.
    from pyflic.base.ui import settings

    monkeypatch.setattr(settings, "_CONFIG_DIR", folder / "pyflic")
    monkeypatch.setattr(settings, "_CONFIG_FILE", folder / "pyflic" / "ui.json")
