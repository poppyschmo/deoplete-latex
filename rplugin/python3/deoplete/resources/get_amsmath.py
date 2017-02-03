# =============================================================================
# ---------------- Scrape AmS "ldoc" and AmS "primer" template ----------------
# =============================================================================
# This script mimics the procedure from ``get_lshort.py``, which is better
# documented.
#
# NOTE - all types in output data are strings (only applies to this script).
#
# Re longevity and brittleness: CTAN seems like the only source for
# this stuff, but their archive does not preserve a version history. Without a
# VCS, revisions can't be pinned.
#
# TODO - excise AmS source retrieval from makefile and include output of this
# script for hard coding into dependent "union/merge" scripts i.e.,
# effectively, make this a one-off.
#
# XXX - Length difference for old lshort - amsstuff = 167
# XXX - Template stuff must be tagged as not belonging to an actual package.

import json
import os
import re
from itertools import chain

from common.fpaths import get_lines, save_backup

CWD = os.curdir if __name__ == "__main__" else os.path.dirname(__loader__.path)

OUTFILES = ('lists/amsmath.json', 'lists/amshelp_template.json')
SRCFILES = ('data/amshelp/template.tex', 'data/amsmath/amsldoc.idx')

ams_help_template, amsmath_ldoc = get_lines(*SRCFILES, cwd=CWD)

# Form set of tripples like ``('amsart', 'class', 42), ... ``
triplets_RE = re.compile(
    r'\\indexentry\{[^{+]+[{+]([^}+]+)[}+]\s?([^{|]*)(?:[|][^{]+)?}\{(\d+)\}')

def ams_trip_test(line):
    rejects = ('\\see{', '\\@\\verb"')
    m = triplets_RE.match(line)
    if m and any(s in m.group(1) for s in rejects):
        return False
    if m and (all(m.groups()) or m.group(1).startswith('\\')):
        return True
    return False

ams_trips = {triplets_RE.match(line).groups() for line in amsmath_ldoc if
             ams_trip_test(line)}

# Split m.group(1) from match groups like ``("\\foo \\bar \\baz", "", 42)``
concatenated = ((('command', command, 'math') for command in mg_one) for
                mg_one in (g[0].split() for g in ams_trips if ' ' in g[0]))

# Save for below...
unnested = list(chain.from_iterable(concatenated))
del concatenated

# Assign 'math' mode to all commands, ditch page numbers.
ams_trips = {(cat if cat else 'command', name, 'text' if cat else 'math') for
             name, cat, page in ams_trips if ' ' not in name} | set(unnested)

# A handful of unofficial but common macros from amsthm:
template_RE = re.compile(r'^\\new\w+{([^}]+)}[^{]*{([^}]+}?)}')
tem_reap = (template_RE.match(line).groups() for
            line in ams_help_template if template_RE.match(line))

tem_quads = [('command' if nm.startswith('\\') else 'environment', nm,
              'math' if nm.startswith('\\') else 'text', meta) for
             nm, meta in dict(tem_reap).items()]
del tem_reap

# Make hash map like {name: {type name mode meta }, ... }
def to_dict(tups):
    """Rearrange values structure to mimick namedtuple in get_lshort.
    """
    from get_lshort import foisted_modes
    outdict = {}
    for cat, name, mode, *rest in tups:
        vdict = {'name': name, 'type': cat, 'mode': (mode,), 'meta': None}
        for fm, fnames in foisted_modes.items():
            if name in fnames:
                vdict['mode'] = (fm,)
        # never runs on rev 2.3 of "ldoc". So, for now...
        assert name not in outdict
        # if name in outdict:
        #     vdict = dict(outdict[name])
        #     vdict['type'].add(cat)
        #     vdict['mode'].add(mode)
        #
        # Add meta info for ams stuff:
        meta = {}
        if 'option' in cat:
            meta.update(package='amsmath')
        if rest:
            if cat == 'environment':
                meta.update(ams=('AmS theorem: "%s"' % rest.pop()))
            elif cat == 'command':
                meta.update(ams=('AmS macro: "%s"' % rest.pop()))
        if meta:
            vdict.update(meta=meta)
        outdict.update({name: vdict})
    return outdict

amshelp = to_dict(tem_quads)
amsmath = to_dict(ams_trips)

if __name__ == "__main__":
    for outfile, outdict in zip(OUTFILES, (amsmath, amshelp)):
        save_backup(CWD, outfile)
        with open(os.path.join(CWD, outfile), 'w') as f:
            json.dump(outdict, f, indent=2, sort_keys=True)

#################
#   debugSLUG   #
#################
# raise SystemExit
#################
