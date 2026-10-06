class Panel:
    """A widget whose setup passes a dedented literal."""

    def setup(self):
        self.text = make("""
{
    "role": "user",
# not a comment, string content
}
        """.strip())
        self.ready = True

    def other(self):
        return call(
1, 2)

    def pick(self, a):
        x = 1 if a \
            else 2
        return x
