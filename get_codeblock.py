#!/usr/bin/env python3
"""get_codeblock - Get code block containing a line in a file."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from get_codeblock.core import main

if __name__ == "__main__":
    main()
