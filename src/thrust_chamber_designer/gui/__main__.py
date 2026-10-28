import sys

from .app import main

if __name__ == "__main__":
    # the guard keeps the thermal simulation process, which imports this module again, from opening a second window
    sys.exit(main())
