"""Delegate-core helpers — REQ-003 fixture (a package two levels deep, whose PARENT dir
('plugin') is deliberately NOT a declared package, and whose OWN dir has a hyphen)."""


def pop_ack(args):
    return args


def mark_incompatible():
    return None


def prepare_self_delegate(assistant_message, self_obj, messages):
    return assistant_message, self_obj, messages
