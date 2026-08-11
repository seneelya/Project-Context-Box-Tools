#!/usr/bin/env python3
"""get_codeblock - Get code block containing a line in a file."""

import sys
from pathlib import Path

# Force UTF-8 stdout: block text is written byte-for-byte and may contain chars the
# Windows console cp1251 codec can't encode (→, cyrillic, …), which would crash mid-output.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from get_codeblock.core import main

if __name__ == "__main__":
    main()
