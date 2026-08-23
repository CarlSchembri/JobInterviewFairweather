#!/usr/bin/env python3
"""Package the game as a single double-clickable executable.

    python -m pip install pyinstaller
    python build_exe.py

PyInstaller is a *build-time* tool only. The executable it produces still has
zero runtime dependencies — it is the same standard-library game with a Python
interpreter stapled to the front, so `python game.py` keeps working unchanged.

The console window is deliberate, not an oversight: the per-turn ledger diff is
grading evidence and has to stay visible.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "FairweatherTransit"


def main():
    try:
        import PyInstaller.__main__
    except ImportError:
        print("PyInstaller is not installed. Run:\n\n    python -m pip install pyinstaller\n")
        return 1

    sep = os.pathsep                       # ';' on Windows, ':' elsewhere
    args = [
        os.path.join(HERE, "game.py"),
        "--name", NAME,
        "--onefile",
        "--console",                       # the ledger diff has to stay visible
        "--distpath", HERE,                # beside the source, not buried in dist/
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build"),
        "--add-data", "%s%s%s" % (os.path.join(HERE, "static"), sep, "static"),
        "--add-data", "%s%s%s" % (os.path.join(HERE, "world_bible.md"), sep, "."),
        "--clean",
        "--noconfirm",
    ]
    print("Building %s…\n" % NAME)
    PyInstaller.__main__.run(args)

    exe = os.path.join(HERE, NAME + (".exe" if os.name == "nt" else ""))
    if not os.path.isfile(exe):
        print("\nBuild finished but %s is missing." % exe)
        return 1

    size = os.path.getsize(exe) / (1024 * 1024)
    print("\n" + "=" * 66)
    print("  Built: %s  (%.1f MB)" % (exe, size))
    print("  Double-click it. ledger.json, transcript.txt and logs/ are written")
    print("  next to the executable.")
    print("=" * 66)

    # The intermediate build trees are large and regenerated every time.
    shutil.rmtree(os.path.join(HERE, "build"), ignore_errors=True)
    shutil.rmtree(os.path.join(HERE, "dist"), ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
