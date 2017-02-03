
from collections import abc


def is_seq(s):
    """Return True if sequence is list or tuple or some facsimile.
    Reject dictionary views, memoryview, bytearray, array.array etc.
    """
    if isinstance(s, abc.Sequence) and not isinstance(s, (str, bytes)):
        return True
    return False


def enlist(*args, ret_type=tuple):
    """Take a combinations of strings and sequences, consolidate.
    """
    inset = set()
    for s in args:
        if isinstance(s, str):
            inset.add(s)
        # can be tuple, list, set, etc...
        if not isinstance(s, str) and isinstance(s, abc.Sequence):
            inset |= set(s)
    return tuple(sorted(inset)) if ret_type is tuple else sorted(inset)
