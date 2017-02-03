#!/bin/python3
"""Export compacted json file. ``sort_keys=True`` is hard coded."""

import json
import sys

from common.fpaths import is_path

if __name__ == "__main__":

    if is_path(sys.argv[2]):
        print('File "%s", exists, clobbering...' % sys.argv[2],
              file=sys.stderr)

    if is_path(sys.argv[1]):
        with open(sys.argv[1]) as f:
            data = json.load(f)

    with open(sys.argv[2], 'w') as g:
        json.dump(data, g, separators=(',', ':'), sort_keys=True)
