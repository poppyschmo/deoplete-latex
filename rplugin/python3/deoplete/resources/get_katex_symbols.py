#!/bin/python3
# =============================================================================
#                    Script to scrape KaTeX symbols.js file
# =============================================================================
# Pinned rev date: 2017 Jan 14
#
# Output structure: sorted OrderedDict
#
#   group_one: {
#           cmd_one: {
#                   mode: str else sorted list if > 1
#                   font: str
#                   atom: str else sorted list if > 1
#                   symbol: char
#                   name: str (same as cmd_one)
#           }
#   }
#
# TODO - rewrite in real javascript or use regexes instead of ``eval()``.
# TODO - fix fundamental flaw with near-dups diffing only in ``mode``.

import os
import re
import json
from urllib import request
from collections import namedtuple
from itertools import chain

from common.fpaths import save_backup

CWD = os.curdir if __name__ == "__main__" else os.path.dirname(__loader__.path)
OUTFILE = 'lists/katex_symbols.json'

url = 'https://raw.githubusercontent.com/Khan/KaTeX/{}/src/{}'
filename = 'symbols.js'
commit = 'bd9db332d2887d884ec7ab3ca68488314b8618da'  # 2017 Jan 14
# commit = 'ec62ec39d82b6b42ee2ec9ad866a79c56b8e2990'  # 2016 Aug 2
# commit = 'master'
URL = url.format(commit, filename)

with request.urlopen(URL) as u:
    uraw = u.read()
usplits = uraw.decode().split('\n\n')
del url, filename, commit, uraw


def preval_replace(s):
    for old, new in (('var ', ''), ('const ', ''),
                     (';\n', ', '), (';', ''), (' = ', '=')):
        s = s.replace(old, new)
    return 'dict(' + s + ')'

def gen_outdict(symbols_it):
    """Without the change of ``ntup.mode`` from str to list, output
    would be roughly equivalent to:
    >>> dict((gname, {ntup.name: ntup._asdict() for ntup in grp})
             for gname, grp in gr_symtups)
    ...
    """
    #
    # TODO change all ``mode`` and ``atom`` vals to lists
    from collections.abc import MutableSequence
    outdict = {}
    for groupname, group in symbols_it:
        newgroup = {}
        for ntup in group:
            # ntup = ntup._replace(mode=[ntup.mode])
            if ntup.name not in newgroup:
                newgroup.update({ntup.name: ntup._asdict()})
            else:
                existing = newgroup[ntup.name]
                for field in 'font symbol'.split():
                    assert existing[field] == ntup._asdict()[field]
                for field in 'atom mode'.split():
                    if isinstance(existing[field], MutableSequence):
                        # For now, this can't exist without implementing above.
                        assert False
                        if ntup._asdict()[field] not in existing[field]:
                            existing[field].append(ntup._asdict()[field])
                            existing[field].sort()
                    else:
                        if existing[field] != ntup._asdict()[field]:
                            existing.update({field: sorted(
                                [existing[field], ntup._asdict()[field]])})
        outdict.update({groupname: newgroup})
    return outdict


# Among the first few lines of the source file are js var initializations for
# creating `module.exports` objects. These take the form: `var foo = "foo";`.
# Snag these and store them as a dict alongside original comment heading.
gr_mxports_RE = re.compile(r'/+\s?\w+:?\n(?:var|const)\s')

# If diff fails because of upstream changes, check these first...
gr_mxports = (grp.split(':\n') for grp in usplits if gr_mxports_RE.match(grp))

gr_mxports = ((group[0].lstrip('/ '), eval(preval_replace(group[1]))) for
              group in gr_mxports)

# Consolidate vars for later use as environment dictionary.
mx_envdict = dict(set.union(*(set(grp[1].items())
                              for grp in gr_mxports)) ^ {("null", None)})

del gr_mxports, gr_mxports_RE

# As of Sep '2016, symbols.js @ the url above has contiguous chunks of call
# statements that create js record objects for each math-mode symbol. Each
# chunk is separated by a double newline:
# ```
#   defineSymbol(math, ams, textord, "\\u2720", "\\\\maltese");
# ```
# Of the six modes (2 vertical, 2 horizontal, 2 math), only math vs non-math
# matters. KaTeX's calls the other 'text', which should suffice.

# All these chunks are labeled with a topside comment in the form '//\w+\n'.
# Later, these chunks will be referred to as KaTeX sym tables (see lshort).
gr_hasname_RE = re.compile(r'[/]+.+\ndefine')
gr_hasname = (grp.splitlines() for grp in usplits if gr_hasname_RE.match(grp))
gr_hasname = ((grp.pop(0).lstrip('/ ').replace('AMS', 'AmS'), grp)
              for grp in gr_hasname)

# These last few don't have labels, so just use "Misc_{A-Z}"...
gr_unnamed_RE = re.compile(r'defineSymbol[^;]+;\n')
gr_unnamed = (grp.splitlines() for grp in usplits if gr_unnamed_RE.match(grp))
gr_unnamed = (('Misc_' + chr(dex + ord('A')), grp)
              for dex, grp in enumerate(gr_unnamed))

# Create named tuples for each record...
defineSymbol = namedtuple('Symbol', 'mode font atom symbol name')

# Apply saved env vars from above...
gr_symtups = ((grp[0], {eval(line.rstrip(';'), globals(), mx_envdict) for line
                        in grp[1]}) for grp in chain(gr_hasname, gr_unnamed))

del usplits, gr_hasname, gr_unnamed

# ##########
# DEBUG SLUG
# ##########
# raise SystemExit
# ##########

# Output to json file...

if __name__ == "__main__":
    save_backup(CWD, OUTFILE)
    with open(os.path.join(CWD, OUTFILE), 'w') as f:
        json.dump(gen_outdict(gr_symtups), f, indent=2, sort_keys=True)
else:
    outdict = gen_outdict(gr_symtups)

del gr_hasname_RE, gr_unnamed_RE, mx_envdict, gr_symtups
