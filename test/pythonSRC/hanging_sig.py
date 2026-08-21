"""Regression fixture: hanging-indent multi-line signatures.

The closing `) -> T:` sits at the continuation column (aligned under the open paren),
NOT dedented to the header indent. find_colon_line must still end the signature here by
bracket balance; otherwise a def balloons over its siblings (RANGE bug, sweep-caught).
"""


class Api:
    def alpha(self, a: str, *, mode: str = None,
              flag: bool = False) -> str: ...

    def beta(self, keys: str, *, mode: str = None,
             flag: bool = False) -> str:
        return keys
