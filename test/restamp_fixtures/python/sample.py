"""Sample module for merge-identity manual tests (REQ-004+005)."""


def unchanged_fn(x):
    return x


async def became_async_fn(x, extra=None):
    return x


def check_value(x):
    return x


def brand_new_fn(x):
    return x
