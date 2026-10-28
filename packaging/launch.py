# Entry script of the packaged desktop app (PyInstaller). The guard matters: the thermal simulation runs in a process that imports
# this script again, and must not open a second window.
import sys

from thrust_chamber_designer.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
