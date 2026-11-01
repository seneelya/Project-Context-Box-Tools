"""Minimal Point accessor ownership probe; no grammar, parser, ctypes or source file."""
import json
import sys
from tree_sitter import Point


def measure(accessor):
    point = Point(100000, 200000)  # Values outside CPython's immortal small-int cache.
    value = point[0 if accessor != 'column' else 1]
    before = sys.getrefcount(value)
    if accessor == 'row':
        item = point.row
    elif accessor == 'column':
        item = point.column
    else:
        item = point[0]
    during = sys.getrefcount(value)
    del item
    after = sys.getrefcount(value)
    # Print only copied counts; do not repeat the faulty getter on damaged objects.
    return dict(accessor=accessor, before=before, during=during, after=after,
                expected_delta=[1, 0], actual_delta=[during - before, after - before])


if __name__ == '__main__':
    print(json.dumps(measure(sys.argv[1] if len(sys.argv) > 1 else 'row')))
