#!/bin/python3
# =============================================================================
# **********************  Consolidate KaTeX and lshort  ***********************
# =============================================================================

import os
import sys
import json
import unicodedata

from itertools import chain

from common.fpaths import save_backup
from common.types import enlist, is_seq

from get_katex_symbols import outdict as ktsyms_src
from get_katex_wiki import outdict as ktwiki_src
from get_lshort import outdict as lshort_src
from get_amsmath import amsmath as amsmath_src
from get_amsmath import amshelp as amshelp_src

# Disable this if either AmS source change and run a diff.
# "data/amsmath/amsldoc.tex" (2.09, 2004, Apr 6)
# "data/amshelp/amshelp.tex (2.3, 2013, Jan 28)
USEAMS = True

CWD = os.curdir if __name__ == "__main__" else os.path.dirname(__loader__.path)
OUTFILE = 'lists/union_katex_lshort.json'


# These are just for inspection/repling...
lshort_names = lshort_src.keys()
ktwiki_names = ktwiki_src.keys()
ktsyms_names = set.union(*(set(d.keys()) for d in ktsyms_src.values()))

# KaTeX's lists have some commands that aren't in lshort
diff_ktsyms_lshort = ktsyms_names - lshort_names
diff_ktwiki_lshort = ktwiki_names - lshort_names

# Fold AMS into lshort
def merge_ams(amsmath, amshelp, lshort):
    for amsk, amsv in chain(amsmath.items(), amshelp.items()):
        if amsk not in lshort:
            lshort.update({amsk: amsv})
            continue
        lvdict = lshort[amsk]
        for k, v in amsv.items():
            # Can't just check ``__contains__`` here bec. some vals are None.
            if k not in lvdict or (v in lvdict[k] if is_seq(lvdict[k]) else
                                   v == lvdict[k]):
                continue
            if k not in ('name', 'meta'):
                lvdict.update({k: enlist(v, lvdict[k])})
            elif k == 'meta' and v is not None:
                if lvdict['meta'] is None:
                    lvdict['meta'] = {}
                for mk, mv in v.items():
                    if mk not in lvdict['meta']:
                        lvdict['meta'].update({mk: mv})
                    else:
                        # This doesn't run, but add concat logic if that
                        # ever changes.
                        pass
            else:
                assert v is None

if USEAMS is True:
    merge_ams(amsmath_src, amshelp_src, lshort_src)

# Helper for following loop.
def replace_atoms(atom):
    pairs = (('textord', 'ord (text)'), ('mathord', 'ord'), ('accent', 'acc'))
    try:
        for old, new in pairs:
            atom = atom.replace(old, new)
    except AttributeError:
        # XXX - consider dropping or stringifying like ``', '.join(...)``.
        return tuple(replace_atoms(a) for a in atom)
    return atom.capitalize()

# Merge KaTeX symbols.js stuff first
master_base = dict(lshort_src)
ktsyms_chck = set(ktsyms_names)
for grpname, grpdict in ktsyms_src.items():
    for kname, vdict in grpdict.items():
        # Deal with dupllicates first.
        if kname in ktsyms_chck:
            ktsyms_chck.remove(kname)
        else:
            # Merge modes when duplicates found.
            if master_base[kname]['mode'] != vdict['mode']:
                nmode = enlist(vdict['mode'], master_base[kname]['mode'])
                master_base[kname].update(mode=nmode)
            # XXX - Justify why this exists, else delete...
            if ('katable' in master_base[kname]['meta'] and
                    master_base[kname]['meta']['katable'] != grpname and
                    'Misc_' not in grpname):
                print('Cap. conflict w. %s: %s(new) -> %s(existing)' % (kname,
                      grpname, master_base[kname]['meta']), file=sys.stderr)
                raise SystemExit
            continue
        # Change mode type to tuple in ktsyms.
        vdict.update(mode=enlist(vdict['mode'], vdict['mode']))
        # Add missing 'type' key as 'command':
        vdict.update([('type', 'command')])
        # Remove KaTeX font data
        vdict.pop('font')
        # These should correspond to atoms in Chapter 17 of The TeXbook.
        atom = replace_atoms(vdict.pop('atom'))
        # When master doesn't yet have entry for kname...
        master_base.setdefault(kname, vdict)
        # Add unicode name to info string.
        new_symbol = master_base[kname].setdefault('symbol', vdict['symbol'])
        uniname = unicodedata.name(new_symbol, None) if new_symbol else None
        katable = grpname if 'Misc_' not in grpname else None
        #
        for mkey, mval in zip(('atom', 'katable', 'uniname'),
                              (atom, katable,
                               uniname.lower() if uniname else uniname)):
            if (master_base[kname].setdefault('meta', None) is not None and
                    mkey in master_base[kname]['meta']):
                raise Exception("dup found: %s" % kname, vdict)
            if mval:
                if master_base[kname]['meta'] is None:
                    master_base[kname]['meta'] = {}
                master_base[kname]['meta'].update([(mkey, mval)])

# Verify dup counter:
if len(ktsyms_chck) != 0:
    print('Duplicate check failed...', file=sys.stderr)
    raise SystemExit

# Pad missing symbol key with null val
for kname, vdict in master_base.items():
    vdict.setdefault('symbol', None)

# The wiki stuff goes last because it has the least precise info, e.g., all
# ``mode`` vals are hard coded to ``"math"``.
for kname, vdict in ktwiki_src.items():
    if kname not in master_base:
        master_base.update({kname: vdict})

# Save a copy
if __name__ == "__main__":
    save_backup(CWD, OUTFILE)
    with open(os.path.join(CWD, OUTFILE), 'w') as f:
        json.dump(master_base, f, indent=2, sort_keys=True)


#################
#   debugSLUG   #
#################
# raise SystemExit
#################
