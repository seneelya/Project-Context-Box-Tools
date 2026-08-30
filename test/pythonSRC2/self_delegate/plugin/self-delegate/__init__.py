"""REQ-003 fixture: relative import of a sibling module inside a nested, hyphenated package
whose parent directory ('plugin') has no `__init__.py` of its own."""

from . import delegate_core


def run(args, assistant_message, self_obj, messages):
    result = delegate_core.pop_ack(args)
    delegate_core.mark_incompatible()
    delegate_core.prepare_self_delegate(assistant_message, self_obj, messages)
    return result
