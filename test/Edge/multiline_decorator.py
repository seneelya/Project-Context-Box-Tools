import pytest


@pytest.mark.parametrize(
    "x, y",
    [(1, 2), (3, 4)],  # a ")" in a comment: )
)
@pytest.mark.slow
def test_pair(x, y):
    assert x < y


def plain():
    return 1


@dataclass(
    frozen=True,
)
class Point:
    x: int = 0

    @app.get(
        "/p",
        tags=["(x"],
    )
    def get(self):
        return self.x
