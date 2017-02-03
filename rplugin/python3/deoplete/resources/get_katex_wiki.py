#!/bin/python3

import os
import re
import json

from common.fpaths import save_backup, check_commit

CWD = os.curdir if __name__ == "__main__" else os.path.dirname(__loader__.path)
SRCFILE = 'data/KaTeX.wiki/Function-Support-in-KaTeX.md'
OUTFILE = 'lists/katex_wiki.json'
PINNED_REV = '936af76133a0049d345effc0b2fff23574332a2c'  # 2017 Jan 16

check_commit(os.path.dirname(SRCFILE), PINNED_REV, bail=True)

with open(os.path.join(CWD, SRCFILE)) as f:
    kw_raw = f.read()

sectioned_RE = re.compile(r'\n\n+(?![`])')
sectioned = sectioned_RE.split(kw_raw)

del f, kw_raw, sectioned_RE

trimmed_RE = re.compile(r'^\w.*\n\n.*([`].+[`].*\n?)(.*\n?)*$')
trimmed = (trimmed_RE.match(span).group()
           for span in sectioned if trimmed_RE.match(span))

command_RE = re.compile(r'`(.*?)`')
title_RE = re.compile(r'^[^\n]+')
# Obsolete format used by earlier attempts (keep around just in case)...
outdict = dict((title_RE.match(grp).group(), command_RE.findall(grp)) for
               grp in trimmed)

del sectioned, trimmed, trimmed_RE, command_RE, title_RE

# Easier to work with in "meld" scripts, but > 10x size of the other.
def conform(indict):
    outdict = {}
    for cap, coms in indict.items():
        for com in coms:
            cat = 'environment' if 'Environ' in cap else 'command'
            if cat == 'command' and not com.startswith("\\"):
                # Exclude: ``~'()[]|=/+-``
                continue
            katable = cap + ' (KaTeX wiki).'
            vdict = {'name': com, 'type': cat, 'mode': ('math',),
                     'symbol': None, 'meta': dict(katable=katable)}
            outdict.update({com: vdict})
    return outdict


if __name__ == "__main__":
    save_backup(CWD, OUTFILE)
    with open(os.path.join(CWD, OUTFILE), 'w') as f:
        json.dump(outdict, f, indent=2, sort_keys=True)
else:
    outdict = conform(outdict)
