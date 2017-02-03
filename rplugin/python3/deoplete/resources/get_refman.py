#!/bin/python3
# =============================================================================
# *************************** Get Reference Manual ****************************
# =============================================================================
# Source : LaTeX2e: An unofficial reference manual
# url: `http://home.gna.org/latexrefman`
#
# TODO: Script is obsolete. Current purpose is merely to provide boolean noting
# presence of a latex2e entry for a given command. Use tags file instead.
# TODO: Add 'env' property to 'meta' because some commands only operate in a
# given environment. XXX - Check if this still applies.

import re
import os
import json

from common.fpaths import is_path, save_backup

CWD = os.curdir if __name__ == "__main__" else os.path.dirname(__loader__.path)

OUTFILE = 'lists/refman_idx.json'

SRCFILES = ('data/latex2e.texi', 'data/latex2e.info')

for fpath in SRCFILES:
    is_path(fpath, bail=True)

with open(SRCFILES[0], encoding='latin1') as f:
    texi_raw = f.read()

with open(SRCFILES[1]) as f:
    info_raw = f.read()


# Create "alternate" doc strings ----------------------------------------------

# Use dirty regexes to target  `@findex` lines in texinfo source...
spl_idx = texi_raw.split('\n@findex ')
spl_cmd = (s for s in spl_idx if s.startswith('\\') and not
           s.startswith('\\\\') and not s.startswith('\\]'))
spl_exp = (s for s in spl_cmd if '\n@example' in s)

exp_RE = re.compile(r'^(?:.*\n)+?@example\n((?:.*\n)+?)@end')
var_RE = re.compile(r'@var{([^}]+?)}')

first_exp = ((s.partition('\n')[0].partition(' ')[0].partition('@')[0],
              var_RE.sub(
                  r'\1', exp_RE.match(s).group(1).strip('\n')
              ).replace('@{', '{').replace('@}', '}')) for s in spl_exp)

# Get rid of non-commands previously missed...
ats_RE = re.compile(r'(?:@(?:code|dots)){(.*)?}')
con_RE = re.compile(r'\\{2,}\s?\n\s+')

first_exp = [(x, con_RE.sub('', ats_RE.sub(r'\1', y).replace('@@', '@')))
             for x, y in first_exp if x.lstrip('\\') and
             x.lstrip('\\')[0].isalpha() and x in y]


# -----------------------------------------------------------------------------
# Prepare index lists ---------------------------------------------------------
# -----------------------------------------------------------------------------

# Separate info source into nodes...
ispl_nodes = info_raw.split('\n\x1f\n')
nod_RE = re.compile(r'\sNode:\s([^,]*),\s')
nodes = dict((nod_RE.search(x).group(1), x.splitlines())
             for x in ispl_nodes if nod_RE.search(x))

# Mine command and concept indexes --------------------------------------------
xref_RE = re.compile(r'^\*\s([^:]*):\s*([^.]*)\.\s*\(line\s*(\d+)\)$')
cont_RE = re.compile(r'^\s+\(line\s*\d+\)$')

# Some longish entries wrap around to the next line/list item; must merge those
# with previous line/item for xref_RE to work correctly...
comiter = reversed(nodes['Command Index'])
coniter = reversed(nodes['Concept Index'])
com_idx = [line if not cont_RE.match(line) else next(comiter) + line
           for line in comiter]
con_idx = [line if not cont_RE.match(line) else next(coniter) + line
           for line in coniter]
com_idx.reverse()
con_idx.reverse()

# Some envs labeled `foo <1>` point to multiple nodes; kill these:
hom_RE = re.compile(r'(.*)(\s<\d>)(.*)')
# Split labels by capturing extra info (lab_x) after 1st word and pushing to
# end of tuple. Also account for labels of the form 'environment, foo'.
comset = set((lbl_L if lbl_L != 'environment,' else lbl_R, *rest,
              lbl_R if lbl_L != 'environment,' else lbl_L.strip(','))
             for lbl_L, _, lbl_R, *rest in (
                 (*hom_RE.sub(r'\1\3', label).partition(' '), *rest) for label,
                 *rest in (xref_RE.match(line).groups() for line in com_idx
                           if xref_RE.match(line))))

# For this index, only types (packs, filetypes, etc.) matter...
type_RE = re.compile(r'^(\w+)(?:\s)(package|accent|font|file)')
# This one has (node, line) last instead of in middle...
conset = set((_t, _l, targ) for (_t, _, _l), targ in ((type_RE.sub(r'\2, \1',
             label).partition(', ') if type_RE.match(label) else
             label.partition(', '), tuple(targ)) for label, *targ in (
                 xref_RE.match(line).groups() for line in con_idx
                 if xref_RE.match(line))))
# Actually, it seems the `conset` black is useless. Didn't realize all labels
# for `font`, `file`, etc. are not in imperative "keyword" form (as they'd
# appear in a `*.tex` document) but, rather, descriptions. Only `package`
# labels check out. Thus, purge all but package refs, rearrange, and append...
comset |= set((label, node, lnum, _type) for _type, label,
              (node, lnum) in conset if _type == 'package')

outliers_RE = re.compile(r'[.\\]?[\w\d]+\*?$')
comlist = sorted(comset)
# comlist = list(comset)

outliers = [comlist.pop(comlist.index(m)) for m in comlist.copy()
            if not outliers_RE.match(m[0])]

def clean_outliers(inlist):
    outlist = []
    hits = []
    wargs_RE = re.compile(r'^(\\\w+)[{[]')
    for tup in inlist.copy():
        if len(hits) > 1:
            raise Exception(hits)
        hits = []
        label, *middle, extra = tup
        out_label = label
        out_extra = extra
        is_brace = wargs_RE.match(label)
        # Only took care of `equations,` above; now the rest:
        if label.endswith(',') and extra:
            out_label = label.rstrip(',')
            out_extra = label.rstrip(',') + ' ' + extra
            hits += [label]
        # Some full func sigs are listed `foo[bar]{baz}`; move to extra
        if is_brace:
            out_label = is_brace.group(1)
            out_extra = label if not extra else label + ' ' + extra
            hits += [label]
        # Push/pop
        if hits:
            outlist.append((out_label, *middle, out_extra))
            inlist.remove(tup)
    return outlist

comlist += clean_outliers(outliers)

# -----------------------------------------------------------------------------
# Create doc strings from index list ------------------------------------------
# -----------------------------------------------------------------------------

# "Target" item in dicts refers to Gnu info's xref/target hyperlink lingo...
# '\\foo': { name: '\\foo',
#            mode: ['math', 'text'],
#            type: 'command',
# this --->  targ: [('\\foo', 23), ('Math How To', 42)],
#            meta: [('docstr', 'str'), ('pre', 'existing')] }

# These are for entries whose node/extra info doesn't help with sorting...
type_hints = (('lrbox', 'env'), ('clock', 'opt'))

# Options typically only apply to one command. Here, the only ones given are
# for `documentclass`. NOTE: consider storing all options in command's meta
# dict. Likewise, should also probably tag commands specific to a package as
# being such...
options_nodes = (('Document class options', '\\documentclass'),)

# See `line_adjustments` below...
items_nodes = ('Math symbols', 'Math accents', 'Document classes', 'Floats',
               'Document class options', 'Output files', 'Accents',
               'Low-level font commands', 'Font styles', 'Text symbols',
               'Additional Latin letters', 'Page layout parameters')

exclude_nodes = ('Font sizes', 'Math functions')
first_sen_RE = re.compile(r'^\s*(.+?\.?)\s{2}[A-Z]?')

# Called by ``make_cats``.
def gen_docstring(label, node, lnum, forceFF=False) -> tuple:
    source = nodes[node]
    start, end = (None, None)
    is_example = False
    if node in exclude_nodes:
        return (lnum, 'See docs under "%s"' % node)
    # Xref target appears in a @item list. 'atem' means @item...
    atem = "\x27" + label + "\x27"
    is_item = False
    if atem in source:
        is_item = True
        lnum = source.index(atem)
    elif atem in (line.strip() for line in source):
        is_item = True
        lnum = [i for i, l in enumerate(source) if atem == l.strip()][0]
    elif node in items_nodes:
        is_item = True
        if label not in source[lnum]:
            lmin = lnum - 3 if lnum - 3 > 0 else 0
            while source[lnum] and lnum > lmin:
                lnum -= 1
            while not source[lnum] and lnum < len(source):
                lnum += 1
            while label not in source[lnum] and lnum < len(source):
                lnum += 1
    if label in nodes:
        if 'Synopsis:' in source:
            lnum = source.index('Synopsis:')
        elif 'Synopses:' in source:
            lnum = source.index('Synopses:')
    elif not is_item:
        if source[lnum] and label not in source[lnum]:
            if label in source[lnum - 1]:
                lnum -= 1
            elif lnum < len(source) - 2 and label in source[lnum + 1]:
                lnum += 1
    #
    while lnum < len(source):
        if not source[lnum] and start:
            end = lnum
            break
        elif source[lnum] and not start:
            # The docstring will be an example usage snippet...
            if source[lnum].startswith('Synops'):
                is_example = True
            else:
                # Some "synopses" are merely the command alone; skip these...
                if (is_example and source[lnum].strip() == label and
                        lnum < len(source) - 3 and not source[lnum - 1] and
                        not source[lnum + 1]):
                    is_example = False
                    lnum += 2
                # These are guaranteed decent:
                if (source[lnum].lstrip().startswith('\\begin') and
                        '\\end' not in source[lnum]):
                    is_example = True
                start = lnum
        lnum += 1
    #
    if is_example:
        out_str = '\n'.join(source[start:end])
    else:
        out_str = ' '.join(line.strip() for line in source[start:end])
    # Try grabbing just first sentence...
    if not is_example:
        save1 = ''
        if is_item and out_str.startswith("'" + label):
            save1, _junk, out_str = out_str.partition(' ')
        # # Save next line (helpful for debugging
        #     print('debug before:', label, '\n' + out_str)
        if forceFF and label in out_str:
            while out_str:
                m = first_sen_RE.match(out_str)
                if m and not save1 and label not in m.group(1):
                    out_str = out_str[m.end() - 1:]
                else:
                    out_str = m.group(1) if m else out_str
                    break
        else:
            m = first_sen_RE.match(out_str)
            out_str = m.group(1) if m else out_str
        # Deal with mid-sentence amputees:
        if out_str and out_str[0].islower():
            out_str = '... ' + out_str
        if out_str == '':
            out_str = 'See docs under "%s"' % node
        if is_item and save1:
            out_str = save1 + ': ' + out_str
        # # Save this too (counterpart to above)...
        #     print('debug after:\n', out_str + '\n')
    return (start, out_str)

# Some line numbers are erroneous, especially those involving `items_nodes`.
# This is likely attributable to calling makeinfo sans necessary options,
# and it warrants real investigation. Till then, `gen_docstring()` will
# manually search for wrongly indexed items.
line_adjustments = {'Math symbols': -34}

def make_cats(inlist, alts=first_exp, t_hints=type_hints,
              line_adj=line_adjustments, opts_nodes=options_nodes):
    classes, commands, environments = ({}, {}, {})
    files, options, packages, unknowns = ({}, {}, {}, {})
    out_cats = [classes, commands, environments, files,
                options, packages, unknowns]
    types = ('class', 'command', 'environment', 'file',
             'option', 'package', 'unknown')
    alt_docs = dict(alts)
    opts_nodes = dict(opts_nodes)
    #
    for tup in sorted(inlist):
        label, node, lnum, extra = tup
        # Set out_cat and _type (but not yet out_cat['type'])...
        _type = None
        out_cat = None
        for lab, cat, in t_hints:
            if label == lab:
                _type, *_null = (t for t in types if t.startswith(cat))
        for t, d in zip(types, out_cats):
            if _type and t == _type:
                out_cat = d
                break
            elif not _type and t in extra:
                out_cat = d
                for padded in (t, t + ', ', ', ' + t):
                    extra = extra.replace(padded, '')
                _type = t
                break
        #
        if not _type:
            out_cat, _type = (commands, 'command') if (
                label.startswith('\\')) else (unknowns, 'unknown')
        #
        # Deal with mistaken assignments...
        if _type == 'command' and node in ('Output files', 'TeX engines'):
            out_cat, _type = (unknowns, 'unknown')
        #
        if label not in out_cat:
            out_cat[label] = {'name': label}
        curdict = out_cat[label]
        curdict.setdefault('type', _type)
        #
        if node in line_adj:
            # Nullified by override in gen_docstring; keep anyway for now...
            lnum = int(lnum) + line_adj[node]
        else:
            lnum = int(lnum) - 1
        #
        # XXX - unnecessary, already have meta entry 'refman'
        #
        # # "Targets" here are just orig xref target + line...
        # _targ = dict(curdict.setdefault('targ', {}))
        # curline = dict(_targ).setdefault(node, lnum)
        # _targ.update([(node, curline if curline < lnum else lnum)])
        # # For now, store as list; to change to dictview: `_targ.items()`
        # curdict['targ'] = list(_targ.items())
        #
        # Create "meta" dict and populate w. existing, if present...
        _meta = curdict.setdefault('meta', {})
        if extra:
            existing = _meta['pre'].rstrip('.,;') + ', ' if (
                'pre' in _meta and _meta['pre'] != extra) else ''
            _meta.update([('pre', existing + extra)])
        curdict['meta'] = _meta
        #
        # Get new line number and doc string, compare latter to existing...
        _lnum, _doc = gen_docstring(label, node, lnum)
        if 'doc' not in _meta:
            curdict['meta'].update(doc=_doc)
        else:
            challenger = _doc
            if label in _meta['doc'] and label in challenger:
                ex_dex = _meta['doc'].index(label)
                nu_dex = challenger.index(label)
                if ex_dex < nu_dex:
                    favored = _meta['doc']
                elif nu_dex < ex_dex:
                    favored = challenger
                else:
                    favored = challenger if len(challenger) < len(
                                _meta['doc']) else _meta['doc']
            else:
                favored = challenger if label in challenger else _meta['doc']
            if favored == challenger:
                curdict['meta'].update(doc=favored)
            # Force RE search for label in node...
            if label not in _meta['doc'] and label not in challenger:
                _lnum, _doc = gen_docstring(label, node, lnum, True)
                curdict['meta'].update(doc=_doc)
        # Create new `meta` target entry under `refman`...
        curdict['meta'].update(refman=node)
        #
        # Integrate the doc strings from 1st half of script...
        if label in alt_docs and 'alt_doc' not in curdict['meta']:
            alt = alt_docs[label]
            curdoc = curdict['meta']['doc']
            if (curdoc.lower() != alt.lower() and len(alt) <= len(curdoc)):
                curdict['meta'].update(alt_doc=alt)
        # Add `command` meta item for options type...
        if _type == 'option' and node in opts_nodes:
            curdict['meta'].update(command=opts_nodes[node])
        #
        # Sort modes...
        _mode = set(curdict.setdefault('mode', []))
        if 'math' in node.lower():
            _mode.add('math')
        if 'text' in node.lower() or _type not in ['unknown', 'command']:
            _mode.add('text')
        # For now, set `text` as catch-all...
        if not _mode:
            _mode.add('text')
        curdict['mode'] = sorted(_mode)
        #
    plurals = (s + 's' if not s.endswith('s') else s + 'es' for s in types)
    return dict((t, c) for t, c in zip(plurals, out_cats))


outdict = make_cats(comlist)

# Save a copy
if __name__ == "__main__":
    save_backup(CWD, OUTFILE)
    with open(os.path.join(CWD, OUTFILE), 'w') as f:
        json.dump(outdict, f, indent=2, sort_keys=True)
