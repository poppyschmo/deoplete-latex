#!/bin/python3
# =============================================================================
# ********************  Script to scrape the lshort index  ********************
# =============================================================================
# This script depends on the source files for *The Not So Short Intro. to
# LaTeX2e* by Tobias Oetiker, et. al. Some distros include an 'lshort' package
# among the 'texlive' family. Running 'latexmk' on the 'lshort.tex' source file
# should generate the files needed in one shot (you can also do it manually).
# Otherwise, look here: http://www.ctan.org/tex-archive/info/lshort/english
#
# TODO - would prefer to use lists instead of tuples in output values but
# performance is > 10x slower when debugging with breakpoints. If redoing,
# devise some way to switch dynamically.

import os
import re
import json
from collections import namedtuple

from common.fpaths import get_lines, save_backup

# See ``Makefile`` for pinned revisions.
CWD = os.curdir if __name__ == "__main__" else os.path.dirname(__loader__.path)

OUTFILE = 'lists/lshort_idx.json'

SRCFILES = ('data/lshort/lshort.idx',
            'data/lshort/lshort.toc',
            'data/lshort/lssym.tex')

lshort_idx, lshort_toc, lshort_sym = get_lines(*SRCFILES, cwd=CWD)

# Loot idx and package as tuple like so: (t='type', n='name', p='page')
cats = r'package|font|extension|encoding|environment|command'
trip_RE = re.compile(
            r'\\indexentry\{(%s)s?![^{]+\{(.*)\}[^{]+\{(\d+)\}' % cats)
del cats
gr_trip = [trip_RE.match(line.replace("\\char '134 ", '\\')).groups()
           for line in lshort_idx if trip_RE.match(line)]

# Manual additions (note use of text/math instead of page number)
added_entries = [('package', 'mathtools', 'text'),
                 ('environment', 'exer', 'text')]

# These chapter breaks are subject to version changes and the vagaries of
# compilation; thus, verifying that pages line up seems a waste of time. Likely
# better to just spot check and compare idx and toc for a sampling of commands.

mathbegin_RE = re.compile(r'.*Typesetting Mathematical Formulae\}\{(\d+)\}')
aftermath_RE = re.compile(r'.*Specialities\}\{(\d+)\}')

# Set bounds based on toc info.
lower = int([mathbegin_RE.match(x).group(1)
            for x in lshort_toc if mathbegin_RE.match(x)][0])
upper = int([aftermath_RE.match(x).group(1)
            for x in lshort_toc if aftermath_RE.match(x)][0])


def append_to_pool(add_these, pool):
    for entry in add_these:
        pg = lower - 1 if entry[2] == 'text' else lower + 1
        gr_trip.append((*entry[:2], str(pg)))


append_to_pool(added_entries, gr_trip)

# Manual mode adjustments:
foisted_modes = {'text': ['equation', 'displaymath', '\\eqref'],
                 'math': []}

# Determine members applicable to math mode:
makeEntry = namedtuple('Entry', 'type name mode meta')


def mode_sort(triplets):
    """Mode sorting governed by ch. breaks set in globals().
    """
    outset = set()
    justnames = set()
    # TODO: add graphics pages
    for ty, nm, pT in triplets:
        pg = int(pT)
        modeout = set()
        typeout = {ty}
        if nm in justnames:
            suspects = (s for s in list(outset) if s.name == nm)
            for sus in suspects:
                typeout |= ({*sus.type} if isinstance(sus.type, tuple)
                            else {sus.type})
                if ty in sus.type:
                    modeout |= {*sus.mode}
                outset.remove(sus)
        if ty != 'package' and ((pg >= lower and pg < upper) or
                                (pg == 127 and nm.find('math') != -1)):
            modeout.add('math')
        else:
            modeout.add('text')
        #
        # Deal with outliers:
        modeout |= set([k for k, v in foisted_modes.items() if nm in v])
        #
        justnames.add(nm)
        outset.add(makeEntry(ty if len(typeout) == 1 else
                             tuple(sorted(typeout)), nm,
                             tuple(sorted(modeout)), None))
    return outset

outprep = mode_sort(gr_trip)


# This section tackles the symbols table at the end of the math chapter:
cap_RE = re.compile(r'.*caption\{([^}]*)\}')
sym_RE = re.compile(r'\{([^}]+)\}')
abc_RE = re.compile(r'.*verb\|([^{]+)')
not_RE = re.compile(r'(AB|AAA|a)$')

ranges = zip((x + 1 for x, y in enumerate(lshort_sym)
             if y.find('begin{symbols}') != -1),
             (x for x, y in enumerate(lshort_sym)
             if y.find('end{symbols}') != -1))

gr_sym = dict()

for start, end in ranges:
    cap_interval = ''.join(lshort_sym[start - 5:start]).replace("\\AmS{}",
                                                                'AmS')
    cap_out = cap_RE.search(cap_interval).group(1).rstrip('.')
    comlist = []
    # The 'Alphabets' table is an outlier, so deal with that separately:
    if 'Alphabets' not in ''.join(lshort_sym[start - 5:start]):
        for m in sym_RE.findall(''.join(lshort_sym[start:end])):
            if not not_RE.match(m):
                comlist.append(m)
    else:
        for line in lshort_sym[start:end]:
            m = abc_RE.match(line)
            if m:
                comlist.append(m.group(1))
    gr_sym.update({cap_out: sorted(comlist)})

# This is for cap_fix() below...
latexsym_RE = re.compile(r'(Arrows|Binary Relations|Miscellaneous Symbols)$')


def cap_fix(cap, sym):
    """Manual tweaks to address some niggling issues relating to caption
    disparities and corner cases. Depends on latexsym_RE in globals().
    """
    if cap is None:
        return None
    #
    abc_fix = (('scr', 'mathrsfs'), ('frak', 'amsfonts or amssymb'),
               ('bb', 'amsfonts or amssymb'))
    outstr = cap
    # Make AmS Negated Arrows match Katex description
    if outstr.find('AmS Negated') != -1 and sym.find('arrow') != -1:
        outstr = outstr.replace('Binary Relations and ', '')
    # Another 'Alphabets' anomaly
    if cap.find('Alphabets') != -1:
        for pat, tag in abc_fix:
            outstr += ' (' + tag + ')' if sym.find(pat) != -1 else ''
    # lshort makes it a point to mention this, so might as well...
    if latexsym_RE.match(cap):
        outstr += ' (latexsym)'
    return outstr


# Turns out dealing with 'duplicates' makes this more tedious than anticipated.
# If refactoring, use a dict from the outset instead of tuples. And thus avoid
# having to bake out mutables with every update. See ``get_amsmath.py`` for a
# saner approach.
outdict = dict([(tup.name, tup._asdict()) for tup in outprep])

for cap, coms in gr_sym.items():
    for com in coms:
        nMode = {'math'} if 'Non-M' not in cap else {'math', 'text'}
        # `list(...)` converts, literal bracket form wraps...
        nCap = [('lshort', cap_fix(cap, com))]
        if com in outdict:
            nMode |= {*outdict[com]['mode']}
            if outdict[com]['meta'] and nCap[0] not in list(
                    outdict[com]['meta']):
                oD = dict(list(outdict[com]['meta']))
                if 'lshort' in oD:
                    nlist = sorted([oD.pop('lshort'), nCap[0][1]])
                    oD.update(lshort=(', '.join(nlist)))
                nCap = oD.items()
        outdict.update({com: makeEntry('command', com, tuple(sorted(nMode)),
                        tuple(sorted(nCap)))._asdict()})

# Undo initial plan: turn all 'meta' tuples into dicts:
for k, v in outdict.items():
    if v['meta']:
        v.update(meta=dict(v['meta']))

# Save file
if __name__ == "__main__":
    save_backup(CWD, OUTFILE)
    with open(os.path.join(CWD, OUTFILE), 'w') as f:
        json.dump(outdict, f, indent=2, sort_keys=True)

#################
#   debugSLUG   #
#################
# raise SystemExit
#################
