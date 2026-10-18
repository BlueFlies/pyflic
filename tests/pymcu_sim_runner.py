"""Runs PyMCU's own simulator, ``scripts/simulate_recording.py``, on Windows.

PyMCU's simulator builds a firmware 4.0.0 recording from simulated flies and
passes its records through PyMCU's real record parser, DFM bookkeeping and
data-file writer, beside a ``_truth`` folder of what every well did.  It is
written for the Raspberry Pi: the modules it imports pull in the Pi's I2C,
GPIO and serial libraries, and ``DataGetter`` asks for the "fork" process
context, which Windows lacks.  The simulator uses none of them (it stands in
for the bus with its own ``FakeMP`` and starts no process), so stand-ins are
enough for the imports to succeed, and pyflic's own ``.venv`` runs it.  See
C8 of ``docs/paradigm-analyses-plan.md``; ``tests/test_pymcu_simulator.py``
is the test that uses it.

Usage, from anywhere::

    python -I tests/pymcu_sim_runner.py <PyMCU dir> --out <dir> [--seed N] [...]

Everything after the PyMCU folder goes to the simulator unchanged, except
that a relative ``--out`` is taken from the caller's working directory.  The
runner leaves PyMCU's files alone: it writes no bytecode there, and refuses
an ``--out`` inside the checkout.
"""

from __future__ import annotations

import importlib.machinery
import multiprocessing
import os
import runpy
import sys
import types


class _Stub(types.ModuleType):
    """A stand-in module: any attribute is another stand-in, enough for
    module-level imports and names such as ``serial.Serial`` or
    ``from cobs import cobs``.  Calling one raises, so hardware the simulator
    did use would fail loudly rather than pretend to work."""

    def __getattr__(self, name: str) -> "_Stub":
        if name.startswith("__"):
            raise AttributeError(name)
        return _Stub(f"{self.__name__}.{name}")

    def __call__(self, *args, **kwargs):
        raise OSError(f"{self.__name__}: Raspberry Pi hardware is not available here")


# The modules replaced by stand-ins, by exact top-level name (RPi covers
# RPi.GPIO), and why each one is.  A run of PyMCU 6d1aa42's simulator
# imports serial, smbus2, cobs, busio, board, adafruit_tsl2591 and
# adafruit_si7021.
_STUBBED = frozenset({
    # Imported by PyMCU's modules when the simulator imports them.
    "serial",           # pyserial, the UART to the DFMs (COMM); not in pyflic's .venv
    "cobs",             # the UART's byte framing (COMM); not in pyflic's .venv
    "busio",            # Adafruit Blinka's I2C bus (EnvironmentalMonitor)
    "board",            # Blinka's pin names (EnvironmentalMonitor, SI7021); imports match case,
                        # so PyMCU's own Board.py is still the real one
    "gpiozero",         # the Pi's LEDs and inputs (Board, COMM), imported only on a host named MCU
    # Not imported by PyMCU today: the Linux and Pi layer under the libraries
    # above, so that a new hardware import in PyMCU meets a stand-in here
    # rather than an ImportError on Windows.
    "fcntl",            # Linux-only standard module, which smbus2 and pyserial's POSIX side import
    "RPi",              # RPi.GPIO, the Pi's pins
    "digitalio",        # Blinka's GPIO pins
    "neopixel",         # CircuitPython's LED strips
    "microcontroller",  # CircuitPython's board
})
# Replaced by prefix: smbus and smbus2, the Pi's I2C (COMM, SI7021), and
# the adafruit_* sensor drivers (SI7021, TSL2561, TSL2591).
_STUBBED_PREFIXES = ("smbus", "adafruit_")


class _StubFinder:
    """A meta-path finder that answers for the modules above before the real
    import system looks, so an installed copy is never used either."""

    @staticmethod
    def find_spec(name, path=None, target=None):
        top = name.partition(".")[0]
        if top in _STUBBED or top.startswith(_STUBBED_PREFIXES):
            # A package, so that a submodule import (RPi.GPIO) also comes here.
            return importlib.machinery.ModuleSpec(name, _StubFinder, is_package=True)
        return None

    @staticmethod
    def create_module(spec):
        return _Stub(spec.name)

    @staticmethod
    def exec_module(module):
        pass


def _map_fork_to_spawn() -> None:
    """``DataGetter`` calls ``multiprocessing.get_context("fork")`` when it is
    imported, and Windows has only "spawn".  The simulator holds that context
    but starts no process, so "spawn" serves; every other method is left as
    asked."""
    get_context = multiprocessing.get_context

    def _get_context(method=None):
        return get_context("spawn" if method == "fork" else method)

    multiprocessing.get_context = _get_context


def _inside(path: str, folder: str) -> bool:
    try:
        return os.path.normcase(os.path.commonpath([folder, path])) == os.path.normcase(folder)
    except ValueError:  # on another drive
        return False


def simulator_args(args: list[str], pymcu: str) -> list[str]:
    """*args* with a relative ``--out`` made absolute from the caller's
    working directory, since the simulator runs from PyMCU's.  An ``--out``
    inside the checkout *pymcu* is refused (``SystemExit``)."""
    out = list(args)
    for i, arg in enumerate(out):
        if arg == "--out" and i + 1 < len(out):
            out[i + 1] = target = os.path.abspath(out[i + 1])
        elif arg.startswith("--out="):
            target = os.path.abspath(arg[len("--out="):])
            out[i] = "--out=" + target
        else:
            continue
        if _inside(target, pymcu):
            sys.exit(f"--out {target} is inside the PyMCU checkout, which this runner does not write to")
    return out


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    pymcu = os.path.abspath(argv[0])
    script = os.path.join(pymcu, "scripts", "simulate_recording.py")
    if not os.path.isfile(script):
        sys.exit(f"no PyMCU simulator at {script}")
    sys.argv = [script] + simulator_args(argv[1:], pymcu)
    # PyMCU's modules are imported from its checkout; caching their bytecode
    # would write __pycache__ files into it.
    sys.dont_write_bytecode = True
    sys.meta_path.insert(0, _StubFinder)
    _map_fork_to_spawn()
    # The simulator puts PyMCU's folder on sys.path itself; it is run from
    # there, as PyMCU's own docs say to run it.
    os.chdir(pymcu)
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main(sys.argv[1:])
