"""Regression fixture: indentation-heuristic edge cases the sweep caught on real code.

1. Hanging-indent signatures — closing `) -> T:` at the continuation column, not dedented.
2. Comprehension `for`/`if` inside brackets — must NOT read as loop/statement headers.
3. Soft keywords `match`/`case` used as identifiers (`match = ...`) — not match statements.
All three used to fabricate bogus/ballooning blocks (find_colon_line + is_block_header).
"""


class Api:
    def alpha(self, a: str, *, mode: str = None,
              flag: bool = False) -> str: ...

    def beta(self, keys: str, *, mode: str = None,
             flag: bool = False) -> str:
        return keys


def collect(items):
    names = {
        it.name
        for it in items
        if it.name
    }
    match = _re.search(r"x", "y")     # `match` is an identifier here, NOT a statement
    if match:
        return match.group(0)
    return names
