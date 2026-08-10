#!/usr/bin/env python3
"""get_codeblock - Get code block containing a line in a file."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from get_codeblock.handlers import get_handler


def main():
    """Main entry point."""
    from get_codeblock.core import parse_args

    args = parse_args()

    if not args.file:
        print("Error: --file is required", file=sys.stderr)
        sys.exit(1)

    if not args.line:
        print("Error: --line is required", file=sys.stderr)
        sys.exit(1)

    # Determine language from file extension
    ext = Path(args.file).suffix.lower()
    language_map = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "typescript",
        ".jsx": "typescript",
        ".cs": "csharp",
    }

    language = language_map.get(ext, "python")

    try:
        handler = get_handler(language)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Run handler
    output = handler.run()
    if output is not None:
        print(output)


if __name__ == "__main__":
    main()
