#!/bin/python3

# The aim of this script is to reorganize everything from ``update_mathjax.js``
# and ``get_refman`` by package, roughly mimicking the layout exported by
# ``get_cwl``.  Anything not in a known package can follow two routes: If
# tagged with a ``KaTeX`` or ``MathJax`` meta tag, it'll get dumped in the
# ``misc-web`` package.  Otherwise, it'll end up in a generic ``misc-other``
# package.
#
# TODO - Get rid of checks for "required", i.e. "meta", packages. A meta
# package is one containing only include statements. The "required" packages
# ``tools`` and ``amslatex`` are examples. Instead, just assume all are
# present. The main reason is that not all "required" packages on CTAN contain
# manifests, and parsing readmes isn't worth it.


import os
import json

from get_refman import outdict as RF
from get_unimath import outdict as UD
from get_cwl import packages as CP

from common.fpaths import is_path, save_backup
from common.types import enlist, is_seq

CWD = os.curdir if __name__ == "__main__" else os.path.dirname(__loader__.path)

MJ_SRCFILE = 'lists/update_mathjax.json'
OUTFILES = ('lists/union_mj_refman.json', 'lists/union_cwl.json')
MANIDIR = 'data/manifests'


def get_manifest(name):
    # XXX - Missing as of initial commit: amscls, babel, graphics, latexbug
    #
    # If CTAN's http query interface (which supposedly provides directory
    # listings), were more unreliable, this wouldn't be an issue.
    #
    name2path = {'amslatex': 'amslatex/math/manifest.txt',
                 'cyrillic': 'cyrillic/manifest.txt',
                 'psnfss': 'psnfss/manifest.txt',
                 'tools': 'tools/manifest.txt'}
    #
    mirrors_url = 'http://mirrors.ctan.org/macros/latex/required/'
    url = mirrors_url + name2path[name]
    fpath = os.path.join(CWD, MANIDIR, name + '.json')
    #
    if is_path(fpath):
        with open(fpath) as f:
            outlist = json.load(f)
    else:
        from urllib import request
        with request.urlopen(url) as u:
            uraw = u.readlines()
        outlist = sorted(l.decode().strip().split('.')[0] for
                         l in uraw if l.endswith(b'.dtx\n'))
        if not is_path(MANIDIR):
            os.mkdir(os.path.join(CWD, MANIDIR))
        with open(fpath, 'w') as f:
            json.dump(outlist, f, indent=2, sort_keys=True)
    return outlist

def load_mathjax(fpath):
    is_path(fpath, bail=True)
    with open(os.path.join(CWD, fpath), 'r') as fp:
        mathjax = json.load(fp)
    return mathjax

# Provide updated CP and tool to lookup package by category member
def packs_by_cat():
    pack_coms, pack_envs, pack_opts = {}, {}, {}
    packages = dict(CP)
    #
    for package, packvals in packages.items():
        # Add ``self`` item to each package to hold docstring, type, etc.
        # packvals.update(info=None)
        for category, catvals in packvals.items():
            if not catvals:
                continue
            for cat, pcat in zip(('commands', 'environments', 'options'),
                                 (pack_coms, pack_envs, pack_opts)):
                if category == cat:
                    for item in catvals:
                        # Options need both the package/class and the command:
                        # ``{('class-foo', '\\bar'), ('bazpack', '\\spam')}``
                        if category == 'options':
                            for opt in catvals[item]:
                                curpacks = pcat.setdefault(opt, set())
                                curpacks.add((package, item))
                            continue
                        curpacks = pcat.setdefault(item, set())
                        curpacks.add(package)
                        #
                        # XXX - Skipping ``name`` and ``type`` keys for now...
                        #
                        # Add missing boilerplate struct items to item.
                        # Add symbol to 'commands'.
                        if category == 'commands':
                            catvals[item].setdefault('symbol', None)
                            # These contain deprecated but used commands.
                            if package in ('latex-209', 'latex-l2tabu'):
                                catvals[item].update(symbol='(obsolete)')
                        sig = catvals[item].pop('signature')
                        # Rename ``signature`` to ``sig``.
                        catvals[item].update(sig=sig)
                        # # Rename ``signature`` to ``info``.
                        # catvals[item].update(info=sig)
                        #
                        # Add mode item.
                        catvals[item].setdefault('mode', [])
                        # Add meta, populate with extra stuff.
                        meta = catvals[item].setdefault('meta', {})
                        for m_key in ('classifiers', 'env_aliases',
                                      'environments', 'options'):
                            if m_key in catvals[item]:
                                m_item = catvals[item].pop(m_key)
                                if m_item is not None:
                                    meta.update({m_key: m_item})
    #
    def lookup_packs(category, member):
        for cat, pcat in zip(('commands', 'environments', 'options'),
                             (pack_coms, pack_envs, pack_opts)):
            if cat.startswith(category):
                return pcat.get(member)
    #
    return packages, lookup_packs

# Called last by ``make_packs()``.
def fix_modes(packages, inspect=True):
    """Attempt to fill empty ``mode`` vals with best guess. Currently,
    this means almost everything gets assigned ``['text']``. """
    # XXX - Absent some reliable, authoritative data source, mislabled modes
    # are here to stay. Scraping docs is not an option and relying on
    # (crowdsourced) cwl classifiers lacking.
    #
    # These are for the inspection helper below.
    nomode = []
    hasmode = []
    # Lame kludge to manually tweak modes mislabeled by KaTeX or MathJax.
    force_text = ('color',)
    #
    for pack, pdata in packages.items():
        if not pdata:
            continue
        for cat, cdata in pdata.items():
            if not cdata or cat not in 'commands environments'.split():
                continue
            for entry, edata in cdata.items():
                if inspect:
                    outtup = (pack, cat, entry, edata['mode'])
                if edata['mode']:
                    if pack in force_text:
                        edata['mode'] = enlist(edata['mode'], 'text',
                                               ret_type=list)
                    if inspect:
                        hasmode.append(outtup)
                else:
                    if inspect:
                        nomode.append(outtup)
                    else:
                        if 'math' in pack and cat == 'commands':
                            edata['mode'] = ['math', 'text']
                        else:
                            edata['mode'] = ['text']
    #
    def inspect_modes(withmode=True, ret=False):
        curlist = hasmode if withmode else nomode
        if ret:
            return curlist
        for tup in curlist:
            print('{:<{w}}{:<{w}}{:<{w}}{!r:<{w}}'.format(
                *(s + ': ' for s in tup[:-2]), *tup[-2:], w=20))
        print('\n%s items found.' % len(curlist))
    #
    if inspect:
        return inspect_modes

# Add emtpy classes to make sorting easier.
def add_classes(packs, acats):
    # Classes currently in ``packages``...
    cur_classes = set.union(*(set(cls.partition('-')[-1].split(',')) for
                              cls in packs.keys() if cls.startswith('class')))
    # Needed classes from in ``allcats``.
    missing = acats['classes'].keys() - cur_classes
    generic = 'article book letter report slides'.split()
    #
    infoblurb = 'See "{}" in latexrefman ({}).'
    for classname, classdata in acats['classes'].items():
        fullname = 'class-' + classname
        if classname in missing:
            packs.update({fullname: dict()})
            # A few have a (brief) refman docstring. Use blurb instead.
            if 'refman' in classdata['meta']:
                blurb = infoblurb.format(classname,
                                         classdata['meta']['refman'])
                packs[fullname].update(info=blurb)
        # Populate normal latex classes' ``options`` list with standard class
        # options. A few of these don't apply (are flat out wrong), but the
        # latex compiler will complain when that's the case.
        if classname in generic or classname in missing:
            # Add pointer from ``newclass.options`` to ``misc-others.options``.
            boilerplate = dict(packs['misc-other']['options'])
            assert (packs[fullname].get('options', {}).get('\\documentclass')
                    is None)
            packs[fullname].update(options=boilerplate)
    # Remove ``\\documentclass`` entry from ``misc-other``. References will
    # remain.
    packs['misc-other']['options'].pop('\\documentclass')

# Format hodgepodge of all meta data as a cludge for when no info string found.
def bake_info_string(indict) -> str:
    """Concatenate meta strings into fmt: `Foo: foo; Bar: bar ...`
    #
    Known keys: {'doc', 'alt_doc', 'package', 'lshort',
                 'katable', 'atom', 'ams', 'codepoints',
                 'speaktext', 'uniname', 'pre'}
    """
    odoc, pack, lktab, atom, ams, cpt, uspeak = (None for n in range(7))
    #
    if 'doc' in indict:
        doc = indict['doc']
        odoc = doc.rstrip('\n ')
        if 'alt_doc' in indict:
            adoc = indict['alt_doc'].rstrip('\n ')
            if adoc[:10].lower() == doc[:10].lower():
                odoc = adoc if adoc.count('\n') < doc.count('\n') else doc
            else:
                odoc = adoc if len(adoc) < len(doc) else doc
        # The most usable doc strings from refman start with `\\` and have
        # pseudo call signatures, e.g., `\\foo[BAR]{BAZ}`
        #
        # XXX - Check for breakage, diff, delete:
        od_pfx = '' if '\n' not in odoc else 'From latexrefman:\n'
        odoc = odoc if odoc.startswith("'\\") else od_pfx + odoc
    #
    if pack in indict:
        pack = 'Package: ' + pack
    #
    # lshort and katable are basically the same...
    if 'lshort' in indict:
        lktab = 'L-short table: ' + indict['lshort']
    elif 'katable' in indict:
        lktab = 'KaTeX table: ' + indict['katable']
    #
    if 'atom' in indict:
        atom = ('Atom: ' + (', '.join(indict['atom']) if
                is_seq(indict['atom']) else indict['atom']))
    #
    # ams already has labels
    ams = indict.get('ams', None)
    #
    # Refman @item math nodes include unicode codepoints...
    if 'codepoints' in indict:
        if not (odoc and 'U+' in odoc):
            cpt = 'Codepoint: ' + indict['codepoints']
    #
    if 'speaktext' in indict and 'uniname' in indict:
        de_speak = indict['speaktext'].replace('-', ' ')
        de_uni = indict['uniname'].replace('wards', '')
        speak_words = de_speak.split()
        count = sum([1 for w in speak_words if w in de_uni]) / len(speak_words)
        if count > 2 / 3:
            uspeak = 'Unicode name: "' + indict['uniname'].strip('"') + '"'
        else:
            if set(speak_words) & {'corner', 'set', 'struck', 'times',
                                   'brace', 'sigma', 'omicron', 'period',
                                   'trade', 'plus or minus'}:
                uspeak = 'Speaktext: "' + indict['speaktext'].strip('"') + '"'
            else:
                uspeak = 'Unicode name: "' + indict['uniname'].strip('"') + '"'
    elif 'uniname' in indict:
        uspeak = 'Unicode name: "' + indict['uniname'].strip('"') + '"'
    elif 'speaktext' in indict:
        uspeak = 'Speaktext: "' + indict['speaktext'].strip('"') + '"'
    # docstrings for most commands include unicode names...
    if odoc and uspeak and uspeak.lower().replace(
            'wards', '').replace('-', ' ') in odoc.lower():
        uspeak = None
    #
    outstr = ''
    for s in (odoc, pack, lktab, atom, ams, cpt, uspeak):
        if s:
            sep = '\n' if '\n' in s else ' ' if s.endswith('.') else '; '
            outstr += s + sep
    return outstr.rstrip('; ')

# Value massaging for ``allcats``-related business, delegated from make_packs.
def build_entry(category, key, rf_dict, mj_dict):
    rf = rf_dict.get(key, {})
    mj = mj_dict.get(key, {})
    vdict = {'name': key, 'mode': None, 'type': None, 'meta': {}}
    if category == 'commands':
        sym = mj.get('symbol')
        # Some refman @item commands have unintegrated unicode symbols...
        if not sym:
            docstr = rf.get('meta', {}).get('doc')
            if docstr and 'u+' in docstr.lower():
                ds_start = docstr.lower().find('u+')
                ds_end = docstr.lower().find(' ', ds_start)
                sym = eval('"\\' + docstr[ds_start:ds_end].lower(
                        ).replace('+', '') + '"')
        vdict.update(symbol=sym)
    # Compare types...
    ty = set(enlist(rf.get('type'), mj.get('type'))) - {None}
    if rf and mj and len(ty) > 1:
        # lshort classifies `{\\sl ...}`-like commands as fonts...
        if ty == {'command', 'font'}:
            ty.remove('font')
        # Filetype: lshort uses "extension" while refman uses "file"
        elif ty == {'file', 'extension'}:
            ty = {'filetype'}
        else:
            assert ty == {'environment', 'package'}
    if ty & {'file', 'extension'}:
        ty = {'filetype'}
    vdict['type'] = ty.pop() if len(ty) == 1 else list(ty)
    # Combine modes if not equal...
    vdict['mode'] = sorted(
        set(rf.get('mode', [])) | set(mj.get('mode', [])))
    # Consolidate meta items...
    mjM = mj.get('meta', {})
    rfM = rf.get('meta', {})
    if len((set(mjM.keys()) if mjM is not None else set()) &
           (set(rfM.keys()) if rfM is not None else set())):
        raise Exception('MetaKey Conflict:\n%s\n%s\n%s' % (mjM, rfM))
    outM = {}
    outM.update((list(mjM.items()) if mjM is not None else []) +
                (list(rfM.items()) if rfM is not None else []))
    vdict['meta'] = outM
    # Stringify curated meta items...
    vdict['info'] = bake_info_string(outM)
    return vdict
    #
    # Remove dups from unicode-math list, for outputting difference below.
    if key in UD:
        UD.pop(key)

# Similar to above, but for ``packages`` data.
def update_packs(packages, category, key, web, other, entry, packnames):
    # If changing this string, do the same in ``add_classes``...
    infoblurb = 'See "{}" in latexrefman ({}).'
    # These are universal ``\\documentclass`` options that weren't labeled as
    # such in ``get_refman``. Even though they're (correctly) claimed by other
    # more specialized classes, add them to ``misc-other``.
    if category == 'options':
        if entry['meta'].get('command') == '\\documentclass':
            if ('package' in entry['meta'] and not
                    entry['meta']['package'].startswith('class')):
                entry['meta'].pop('package')
            docopts = other[category].setdefault('\\documentclass', [])
            if key not in docopts:
                docopts.append(key)
                docopts.sort()
    if not packnames:
        # Lots of spam like ``en dash``, etc., are unneeded.
        if category == 'commands' and not key.startswith('\\'):
            return
        # This can't go in outer block because "else" uses signature.
        if 'refman' in entry['meta']:
            blurb = infoblurb.format(key, entry['meta']['refman'])
            if all(s not in entry['info'].lower() for
                   s in ('deprecate', 'obsolete')):
                entry['info'] = blurb
        # XXX - Empty info strings should really be addressed in source scripts
        if entry['info'] == '':
            entry.update(info=None)
        # Add info string to package -> info...
        if entry['type'] == 'package':
            if key in packages and entry['info']:
                assert 'refman' in entry['meta']
                # blurb = infoblurb.format(key, entry['meta']['refman'])
                packages[key].update(info=blurb)
        # Deal with the special case of options...
        if category == 'options':
            mcom = entry['meta'].get('command')
            mpack = entry['meta'].get('package')
            if mpack:
                assert mcom is None
                packopts = packages[mpack][category]
                optdict = packopts.setdefault('\\usepackage', {})
                if key not in optdict:
                    optdict.setdefault(key, None)
                return
        # Toss these in ``misc-web``, otherwise ``misc-other``.
        if any(k in entry['meta'] for k in ('mathjax', 'katable')):
            assert category != 'options'
            if category in web:
                assert key not in web[category]
                if key in ('\\begin', '\\end'):
                    # XXX - This should probably go elsewhere.  Add missing
                    # ``\\begin`` and ``\\end`` commands to ``latex-document``
                    entry.update(mode=['math', 'text'])
                    packages['latex-document']['commands'][key] = entry
                else:
                    web[category][key] = entry
        elif category in other:
            if category == 'options':
                assert mcom is not None
                optlist = other[category].setdefault(mcom, [])
                if key not in optlist:
                    optlist.append(key)
                    optlist.sort()
                return
            assert key not in other[category]
            other[category][key] = entry
        # Ditch all meta items. For these, they are redundant.
        entry.pop('meta')
        entry.pop('type')
        return
    assert category != 'packages'
    for pname in packnames:
        # Deal with the special case of options first...
        if category == 'options':
            pname, pcmd = pname
            mcom = entry['meta'].get('command')
            mpack = entry['meta'].get('package')
            packopts = packages[pname][category]
            # Currently, ``packages -> package -> options`` are just lists, so
            # can't add any reference info... XXX - Consider changing this...
            if not mpack:
                assert mcom and mcom == pcmd
                continue
            assert mpack != pname and mcom and (mpack, mcom) not in packnames
            # XXX - Seems above is a roundabout way of asserting this...
            assert mcom != '\\usepackage'
            # When above assertion fails, must use dict instead of list...
            optlist = packages[mpack][category].setdefault(mcom, [])
            if key not in optlist:
                optlist.append(key)
                optlist.sort()
            continue
        pack = packages[pname][category][key]
        # Prefer signatures from cwl, otherwise refman reference...
        if is_seq(pack['sig']):
            sig = '\n'.join(pack['sig']) + '\n'
        elif pack['sig'] is not None:
            sig = pack['sig'] + '\n'
        else:
            sig = ''
        #
        # XXX - These blurbs don't add any real value. Ultimately, need to
        # get more accurate docstrings or forgo the info/preview feature.
        pack.update(info=None)
        if 'refman' in entry['meta']:
            assert all(s not in entry['info'].lower() for
                       s in ('deprecate', 'obsolete'))
            blurb = infoblurb.format(key, entry['meta']['refman'])
            pack.update(info=(sig + blurb))
            # if len(key) + 1 < len(entry['info']):
            #     if 'See docs' in entry['info']:
            #         pack.update(info=entry['info'])
            #     else:
            #         pack.update(info=(entry['info'] + '\n' + blurb))
            # else:
            #     pack.update(info=(sig + blurb))
        # XXX - The catch-all amalgam of all meta nonsense mainly applies to
        # math commands and is pretty annoying. If searching docstrings
        # were somehow an opton, perhaps they'd be justified...
        #
        # elif entry['info']:
        #     pack.update(info=(sig + entry['info']))
        #
        # Update ``symbol`` and ``mode`` vals...
        if 'symbol' in pack and pack['symbol'] is None:
            pack.update(symbol=entry['symbol'])
        if pack['mode']:
            pack.update(mode=enlist(pack['mode'], entry['mode'],
                                    ret_type=list))
        else:
            pack.update(mode=entry['mode'])
    # XXX - Ensure all meta keys ticked during reckoning. Delete if consistent,
    # but save list; errant keys often added carelessly in dependencies...
    mkeys = ('alt_doc ams atom codepoints command doc katable lshort '
             'mathjax package pre refman speaktext uniname')
    for mkey in mkeys.split():
        if mkey in entry['meta']:
            entry['meta'].pop(mkey)
    assert not len(entry['meta'])

# "main()"
def make_packs(MJ):
    # Create base structure from ``packages`` in ``get_cwl``.
    packages, plut = packs_by_cat()
    #
    # XXX - See todo in front matter.
    # tools = dict(includes=get_manifest('tools'))
    #
    # Create ``web``, and ``other`` misc and meta packages.
    web = dict(environments={}, commands={}, options={})
    other = dict(environments={}, commands={}, options={})
    # ``plut()`` will remain ignorant of updates to these, so they must be
    # queried seperately.
    for np_name, np in zip(('misc-web', 'misc-other'), (web, other)):
        packages.update({np_name: np})
    #
    allcats = dict((k, {}) for k in RF.keys() if
                   k not in ('unknowns', 'files'))
    allcats.update(encodings={}, filetypes={})
    # Category changes: ``filetypes`` -> ``files``, ``unknowns`` -> (removed)
    p2s = {'classes': 'class'}
    for category in allcats:
        rf = (RF[category] if category not in ('filetypes', 'encodings') else
              RF['files'] if category != 'encodings' else {})
        mj = dict((x, y) for x, y in MJ.items() if
                  enlist(y['type'], y['type']) == enlist(p2s.setdefault(
                      category, category.rstrip('s')), y['type']))
        #
        if category == 'commands':
            mj.update((x, y) for x, y in MJ.items() if y['type'] == 'font')
        elif category == 'filetypes':
            mj.update((x, y) for x, y in MJ.items() if
                      y['type'] == 'extension')
        #
        # Consolidate entry vals in cat and package dicts.
        for key in rf.keys() | mj.keys():
            # Split off procedural logic, continued here...
            allcats[category][key] = build_entry(category, key, rf, mj)
            # Likewise for dealing with packages...
            update_packs(packages, category, key, web, other,
                         dict(allcats[category][key]), plut(category, key))
            #
    fix_modes(packages, inspect=False)
    add_classes(packages, allcats)
    return allcats, packages


allcats, packages = make_packs(load_mathjax(MJ_SRCFILE))

# Save lists...
if __name__ == "__main__":
    for outfile, outdict in zip(OUTFILES, (allcats, packages)):
        save_backup(CWD, outfile)
        with open(os.path.join(CWD, outfile), 'w') as f:
            json.dump(outdict, f, indent=2, sort_keys=True)
