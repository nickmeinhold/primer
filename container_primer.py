#!/usr/bin/env python3
"""Back-compat shim: the containers/comonads Primer now runs on the generic
engine (primer.py) with its book at books/containers-and-comonads.md.

    python3 container_primer.py   ==   primer --book containers-and-comonads
"""

import os
import sys

sys.argv = [sys.argv[0], "--book",
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "books", "containers-and-comonads.md")]

import primer

if __name__ == "__main__":
    try:
        primer.main()
    except KeyboardInterrupt:
        print("\n\n📖  The book closes gently, keeping your place.\n")
