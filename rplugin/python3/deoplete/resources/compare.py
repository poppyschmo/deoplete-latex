#!/bin/python3

"""
Diff two ``.json`` output files with different mtimes from the same
``get_*.py`` script.  Use ``/bin/diff`` first if script uses
ordered dicts and passes ``sort_keys`` option to ``json.dump()``.

Better with PyPI package ``deepdiff``_.

.. _deepdiff: https://github.com/seperman/deepdiff
"""
try:
    from deepdiff import DeepDiff
except ImportError:
    pass
else:
    from pprint import pformat

import sys
import json
from collections import abc


def fake_deepdiff(one, two, indent=4, path=None, strict_strings=None):
    """Compare two term dictionaries. ``strict_strings=False`` treats
    strings that contain the same combination of words as equal.
    """
    for k, v in one.items():
        _one = v
        _two = two.get(k)
        if _one == _two:
            continue
        if all(isinstance(d, abc.MutableMapping) for d in (_one, _two)):
            _path = path if path is not None else []
            _path += ['{:<{width}}{}'.format('', k, width=indent)]
            fake_deepdiff(_one, _two, indent + 4, _path, strict_strings)
            continue
        if (all(isinstance(l, abc.MutableSequence) for l in (_one, _two)) and
                set(tuple(x) for x in _one if isinstance(x, abc.Sequence)) ==
                set(tuple(x) for x in _two if isinstance(x, abc.Sequence))):
            continue
        if all(isinstance(l, str) for l in (_one, _two)):
            if (strict_strings is False and
                    set(c.strip(';:,.?=_-\n') for c in _one.split()) ==
                    set(c.strip(';:,.?=_-\n') for c in _two.split())):
                continue
            else:
                _one = _one.strip().replace('\n', '')
                _two = _two.strip().replace('\n', '')
        print('\n'.join(path) if path else '')
        print('{:<{width}}{}'.format('', k, width=indent))
        print('{:<{width}}one: {}'.format('', _one, width=indent + 4))
        print('{:<{width}}two: {}'.format('', _two, width=indent + 4))

def fold_dd(dob, levels=2, indent=2, counter=0):
    if counter == levels:
        for item in pformat(dob, indent=indent).split('\n'):
            print('{:<{i}}{}'.format('', item, i=(counter * indent)))
        return
    try:
        for k, v in dob.items():
            print('{:<{i}}{}:'.format('', k, i=(counter * indent)))
            fold_dd(v, levels=levels, counter=(counter + 1))
    except AttributeError:
        for item in dob:
            print('{:<{i}}{}'.format('', item, i=(counter * indent)))

def dd_wrap(one, two):
    if 'DeepDiff' in globals():
        dd = DeepDiff(one, two, ignore_order=True, report_repetition=True)
        fold_dd(dd, 2)
    else:
        fake_deepdiff(one, two)


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        d1 = json.load(f)
    with open(sys.argv[2]) as g:
        d2 = json.load(g)
    #
    if 'DeepDiff' in locals():
        dd = DeepDiff(d1, d2, ignore_order=True, report_repetition=True)
        fold_dd(dd, 2)
    else:
        fake_deepdiff(d1, d2)
