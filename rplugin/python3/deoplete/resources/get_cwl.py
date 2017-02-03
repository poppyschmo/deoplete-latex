#!/bin/python3
# =============================================================================
# ---------------- Scrape signatures from TeX Studio cwl files ----------------
# =============================================================================
# Sources: https://hg.code.sf.net/p/texstudio/hg/
# Spec:    http://texstudio.sourceforge.net/manual/current/usermanual_en.html\
#          #CWLDESCRIPTION
#
# TODO add remaining classifiers to ``get_tests()``

import json
import os
import re
from collections import abc

from common.fpaths import check_commit, save_backup
from common.types import enlist

# Prefer file i/o occur in local module's dir...
CWD = os.curdir if __name__ == "__main__" else os.path.dirname(__loader__.path)
SRCFILE = 'data/texstudio/completion'
OUTFILE = 'lists/texstudio_cwl.json'
PINNED_REV = '89b651aae5cf74f66dc3a183679706841b9bc994'  # 2017 Jan 14

# Splits for commands like ``\left(`` will fail. These are uniques, though, so
# they'll be skipped anyway.
sep_RE = re.compile(r'(\\\w+[*]?)|(\([^)]*\))|({[^}]*})|(\[[^]]*\])|(<[^>]*>)')

cmd_RE = re.compile(r'(\\[^\\[({<\d]+[*]?)')

# Argument fields currently used in completion (key/value pairs are handled
# separately) Sadly, only the "global" ``color`` option is implemented.
ARG_FIELDS = ('color',)


def get_packages(cwl_dir):
    packages = {}
    for cwl_fname in os.listdir(cwl_dir):
        cwl_fpath = os.path.join(cwl_dir, cwl_fname)
        if not cwl_fname.endswith('.cwl') or not os.path.isfile(cwl_fpath):
            continue
        pkgname = cwl_fname.partition('.')[0]
        with open(cwl_fpath, 'r', encoding='UTF-8', errors='replace') as f:
            # Get rid of comments and newline endings
            lines = [l.strip() for l in f.readlines() if l.strip()]
            # rename mislabeled/hybrid class-packages:
            if any(l.startswith('# mode') and
                   ('class' in l or '.cls' in l) for l in lines):
                pkgname = ('class-' + pkgname if not
                           pkgname.startswith('class-') else pkgname)
            packages[pkgname] = {}
            packages[pkgname].update(lines=lines)
            packages[pkgname].update(environments={})
            packages[pkgname].update(commands={})
            packages[pkgname].update(options={})
    return packages

def get_balanced(delims='(){}[]<>'):
    # From <http://stackoverflow.com/a/6753172/4932879>
    iparens = iter(delims)
    parens = dict(zip(iparens, iparens))
    closing = parens.values()
    #
    def _balanced(astr):
        stack = []
        for c in astr:
            d = parens.get(c, None)
            if d:
                stack.append(d)
            elif c in closing:
                if not stack or c != stack.pop():
                    return False
        return not stack
    return _balanced

def get_longer(old, new):
    """Get the longer of two command sequences when one is a superset of
    the other. Otherwise, return a list containing both.
    """
    try:
        pngs = ('\\begin', '\\end')
        old_parts = {x for x in sep_RE.split(old) if x if x not in pngs}
        new_parts = {y for y in sep_RE.split(new) if y if y not in pngs}
        if new_parts == old_parts and new != old and any('\\begin' in c for c
                                                         in (old, new)):
            return old if old.startswith('\\begin') else new
        elif new_parts.issubset(old_parts):
            return old
        elif old_parts.issubset(new_parts):
            return new
        else:
            return [old, new]
    except TypeError:
        # XXX Verify this test is necessary; smells like spam.
        if not isinstance(old, abc.MutableSequence):
            raise TypeError
        # ``new`` must be returned from all combinations to get promoted.
        leaders = set()
        for sig in old:
            res = get_longer(sig, new)
            # Ensure 'foo' doesn't get split into ['f', 'o', 'o']
            winners = (set(res) if isinstance(res, abc.MutableSequence)
                       else set((res,)))
            sigs = (set(sig) if isinstance(sig, abc.MutableSequence) else
                    set((sig,)))
            # ``new`` is always just a string.
            losers = (sigs | set((new,))) - winners
            leaders |= winners
            leaders -= losers
        return sorted(leaders)
    return None

def get_fields(sigs):
    if not sigs:
        return None
    if isinstance(sigs, str):
        sigs = [sigs]
    outset = set()
    for sig in sigs[:]:
        # discard environment name itself
        if sig.startswith('\\begin{') or sig.startswith('\\end{'):
            sig = sig.partition('}')[-1]
        fields = {f.strip('{}()[]<>') for
                  f in sep_RE.split(sig) if f and not f.startswith('\\')}
        outset |= fields
    return outset

def harvest_lines(pack, data, line, in_directive=None):
    """The first half handles options directives. The ``in_directive``
    flag indicates current line resides inside a ``keyvals`` or
    ``ifOption`` comment block. The latter half deals with signatures.
    """
    if in_directive is not None and not line.startswith('#'):
        dtiv_type, dtiv_name = in_directive
        dtiv_name, _junk, classifiers = dtiv_name.partition('#')
        if '\\documentclass' in dtiv_name or dtiv_type == 'ifOption':
            # Non-``\\documentclass`` labels are themselves package options,
            # e.g., ``dvipsnames``. The options that follow pertain to commands
            # belonging to the package, i.e., valid args for various params.
            assert pack.startswith('class-') or '\\document' not in dtiv_name
            dv_cmd, _junk, dv_cls = dtiv_name.partition('/')
            # Most are suffixed like so: ``\documentclass/foo``...
            assert dv_cls in pack if dv_cls else dv_cmd == dtiv_name
            if dv_cmd == '\\documentclass':
                optlist = data['options'].setdefault(dv_cmd, [])
                optlist.append(line.partition('#')[0])
            # One major assumption here is that package option declarations
            # never take the form ``\\command/foo``, like those above. Also,
            # for now, classifiers are just discarded because most aren't yet
            # relevant and preserving them would require some other data
            # layout. 1) The one exception is ``#B``, indicating a color.
            else:
                packopt = data['options'].setdefault('\\usepackage', {})
                optdict = packopt.setdefault(dv_cmd, {})
                option, _junk, opt_classifier = line.partition('#')
                assert opt_classifier
                # Once the option is used in a declaration, its contents will
                # be moved to the appropriate branch under the main ``options``
                # table. So, ``options->\\usepackage->svgnames->color->foo``
                # will be moved to ``options->colors->foo``.
                assert opt_classifier == 'B'  # See (1) directly above...
                colors = optdict.setdefault('color', [])
                colors.append(option)
        else:
            # This also applies if ``dtiv_type == 'keyvals'``. Though the spec
            # doesn't say (probably because it's common knowldege among veteran
            # LaTeX users), these pairs only pertain to the command and are
            # useless elsewhere. That's why they don't go in ``options``.
            #
            # Disallowing ``c`` flags means classifiers will always be ``None``
            classifiers = None if classifiers == 'c' else classifiers
            default = dict(signature=None, classifiers=classifiers)
            curval = data['commands'].setdefault(dtiv_name, default)
            # Initialize if first item...
            curopts = curval.setdefault('options', {})
            curlist = curopts.setdefault(dtiv_type, [])
            # curlist = curval.setdefault(dtiv_type, [])
            curlist.append(line)
        return in_directive
    # Set in_directive flag when options/args directives encountered.
    elif line.startswith('#keyvals') or line.startswith('#ifOption'):
        return line.strip('#').split(':')
    # Save these for good measure (might be wasteful, but whatever).
    elif line.startswith('#include'):
        data.setdefault('includes', [])
        data['includes'].append(line.partition(':')[-1])
        return None
    elif line.startswith('#'):
        return None
    #
    # Main logic for sorting signatures ---------------------------------------
    line, _junk, classifiers = line.partition('#')
    classifiers = (None if not classifiers.lstrip('*') else
                   classifiers.lstrip('*'))
    # Instantiate ``balanced()``...
    balanced = get_balanced()
    # Default value for new entries.
    default = dict(signature=(line if balanced(line) else None),
                   classifiers=classifiers)
    del _junk
    if line.startswith('\\begin') or line.startswith('\\end'):
        envs = data['environments']
        # Grab ``foo`` in ``\\begin{foo}``
        env_name = line.partition('{')[-1].partition('}')[0]
        if env_name == '':
            return None
        old_sig = envs.setdefault(env_name, default).get('signature')
        # Add approporiate items in env_name for classifiers.
        apply_classifiers(envs[env_name], classifiers)
        if old_sig == line:
            return None
        else:
            if not balanced(line):
                return
            winner = get_longer(old_sig, line) if old_sig is not None else line
            if winner == '\\begin{' + env_name + '}':
                winner = None
            envs[env_name].update(signature=winner)
        # Add all options fields, if any, to ``options``
        fields = get_fields(envs[env_name].get('signature'))
        if not fields:
            return
        for arg in ARG_FIELDS:
            if any(a in fields for a in (arg, '%' + arg)):
                assert False  # Never runs as of 89b651aae5cf
                curopts = envs[env_name].setdefault('options', {})
                curopts[arg] = None
    else:
        cmds = data['commands']
        # Absent "insert-cursor" support, treat these tokens as elipses.
        if '%|' in line:
            line = line.replace('%|', '..')
            default.update(signature=line)
        command = cmds.get(line, {}).get('signature')
        # With lines like ``\\begin..\\end``, set all keys to line
        if '..\\' in line or (command and '..\\' in command):
            mpairs = line.split('..')
            if line in mpairs or mpairs is None:
                return None
            assert all(p.startswith('\\') for p in mpairs)
            for mp in mpairs:
                old_sig = cmds.setdefault(mp, default).get('signature')
                # Add approporiate items in env_name for classifiers.
                apply_classifiers(cmds[mp], classifiers)
                if old_sig == line:
                    return None
                # Already a list/MutaSeq, so just tack on.
                if hasattr(old_sig, '__setitem__') and line not in old_sig:
                    old_sig.append(line)
                else:
                    cmds[mp].update(signature=([old_sig, line] if
                                    old_sig is not None else line))
            return None
        cm = cmd_RE.match(line)
        # Arguable whether ``\\left\\foo`` is single or compound.
        if (line.startswith('left') and not line[4].isalpha() and
                line[4] != '\\'):
            command = line
        elif cm:
            command = cm.group(1)
        else:
            return None
        bracks = ('{}', '()', '[]', '<>')
        if not any(all(b in line for b in pair) for pair in bracks):
            # Existing wins even if set to None.
            default.update(signature=None)
            old_sig = cmds.setdefault(command, default).get('signature')
            # Add approporiate items in env_name for classifiers.
            apply_classifiers(cmds[command], classifiers)
            assert (not old_sig or command in old_sig)
            return None
            #
        old_sig = cmds.setdefault(command, default).get('signature')
        apply_classifiers(cmds[command], classifiers)
        if old_sig is None:
            cmds.update({command: default})
        elif old_sig != line:
            if not balanced(line):
                winner = old_sig
            else:
                winner = get_longer(old_sig, line)
            cmds[command].update(signature=winner)
            # Add all options fields, if any, to ``options``
        fields = get_fields(cmds[command].get('signature'))
        if not fields:
            return None
        for arg in ARG_FIELDS:
            if any(a in fields for a in (arg, '%' + arg)):
                curopts = cmds[command].setdefault('options', {})
                if arg not in curopts:
                    curopts[arg] = None

def fill_packages(inpack):
    packages = dict(inpack)
    for pack, data in packages.items():
        in_directive = None
        for line in data['lines']:
            in_directive = harvest_lines(pack, data, line, in_directive)
        else:
            data.pop('lines')
            if not data['environments']:
                data.update(environments=None)
    return packages

def get_tests(echo=None):
    r"""
    {} == 'm'           # math
    {} == 'n'           # text
    {} == 't'           # tabular
    {} == 'T'           # tabbing
    {}.startswith('\\') # env_aliases
    {}.startswith('/')  # environments
    """
    if echo:
        print(get_tests.__doc__)
        return
    from collections import namedtuple
    defs = (s.strip() for s in get_tests.__doc__.split('\n') if s.strip())
    parts = (s.rpartition('#') for s in defs)
    pairs = ((l.strip(), t.strip()) for t, _, l in parts)
    labels, tests = zip(*pairs)
    keys_NT = namedtuple('Classifiers', labels)
    return keys_NT(*tests)

def test_classifier(classifier, test):
    """Test must be repr form of actual test, not its label.
    Example: ``"{} == 'm'"``
    """
    from itertools import repeat
    n = test.count('{}')
    test = test.replace('{}', '{!r}')
    return eval(test.format(*repeat(classifier, n)))

def apply_classifiers(indict, classifier):
    """Create relevant metadata items in category entries"""
    if classifier is None:
        return
    # Freeze/apply ``classifier`` as arg 1.
    from functools import partial
    tc = partial(test_classifier, classifier)
    #
    keys = get_tests()
    force_math = False
    if tc(keys.env_aliases):
        existing = indict.get('env_aliases')
        env_aliases = classifier.lstrip('\\').split(',')
        assert existing is None or set(existing) == set(env_aliases)
        indict.update(env_aliases=env_aliases)
        if 'math' in env_aliases:
            force_math = True
        else:
            return
    elif tc(keys.environments):
        existing = indict.get('environments')
        environments = classifier.lstrip('/').split(',')
        assert existing is None or set(existing) == set(environments)
        indict.update(environments=environments)
        if 'math' in environments:
            force_math = True
        else:
            return
    if force_math is True:
        mode = indict.setdefault('mode', [])
        if 'math' not in mode:
            mode.append('math')
            mode.sort()
            return
    modes = keys._fields[:4]
    modes_res = tuple(map(tc, (keys._asdict()[m] for m in modes)))
    # According to the spec, these mode flags are mutually exclusive, so
    # appending isn't strictly necessary.
    if any(modes_res):
        mode = indict.setdefault('mode', [])
        for m, r in zip(modes, modes_res):
            # Modes other than 'math' and 'text' are invalid. Store them in
            # `environments` instead. See `elif` block above...
            if r and m not in keys._fields[:2]:
                existing = indict.setdefault('environments', [m])
                if existing != [m]:
                    # Never runs as of initial commit.
                    indict.update(environments=enlist(existing, m,
                                                      ret_type=list))
            if r and m not in mode and m in keys._fields[:2]:
                mode.append(m)
        mode.sort()

def inspect_classifiers(packages, test, full=False):
    """Get overview of classifiers present for items in package.
    """
    try:
        test = get_tests()._asdict()[test]
    except KeyError:
        get_tests(1)
        return
    #
    outlist = []
    #
    for pack, pack_conts in packages.items():
        for cat in ('environments', 'commands'):
            if not pack_conts[cat]:
                continue
            view = [(k, v['classifiers']) for
                    k, v in pack_conts[cat].items() if v['classifiers'] and
                    test_classifier(v['classifiers'], test)]
            if view:
                outlist.append((pack, cat,
                                view if full is True else len(view)))
    return outlist

check_commit(os.path.dirname(SRCFILE), PINNED_REV, hg=True, bail=True)
packages = fill_packages(get_packages(os.path.join(CWD, SRCFILE)))

if __name__ == "__main__":
    save_backup(CWD, OUTFILE)
    with open(os.path.join(CWD, OUTFILE), 'w') as f:
        json.dump(packages, f, indent=2, sort_keys=True)
