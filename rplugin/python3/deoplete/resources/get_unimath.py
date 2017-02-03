#!/bin/python3

import os
import re
import sys
import json

# Prefer read/writes happen in local module's dir...
if __name__ == "__main__":
    mdir = sys.path[0] if os.path.isdir(sys.path[0]) else os.curdir
else:
    mdir = os.path.dirname(__loader__.path)

rpath = os.path.join(mdir, 'data/unimath/unicode-math-table.tex')

if not os.path.exists(rpath):
    print('File not found: "%s"...\nQuitting...' % rpath, file=sys.stderr)
    sys.exit()

with open(rpath) as f:
    unimath_raw = f.readlines()

main_RE = re.compile(r'^\\\w+{"([\dA-F]+)}{(\\\w+)\s*}{\\\w+}{(.*)}%\n$')
trip = (main_RE.match(m).groups() for m in unimath_raw)
outdict = {name: {'name': name, 'mode': ('math',),
                  'symbol': eval('"\\u' + sym + '"'),
                  'meta': {'package': 'unicode-math', 'uniname': desc}
                  } for sym, name, desc in trip}

# Save file
dest = os.path.join(mdir, 'lists/unimath.json')

if __name__ == "__main__":
    with open(dest, 'w') as f:
        json.dump(outdict, f, indent=2)

#################
#   debugSLUG   #
#################
# sys.exit()
#################
