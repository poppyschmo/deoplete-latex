# =============================================================================
# ------------------------- LaTeX source for deoplete -------------------------
# =============================================================================

import json
import os
import re

from .base import Base


class Source(Base):

    def __init__(self, vim):
        super().__init__(vim)
        self.name = 'latex'
        self.filetypes = ['tex']
        self.input_pattern = r'[\\([{,]\w*$'
        self.min_pattern_length = 1
        self.mark = "[LaTeX]"
        self.rank = 401

    def on_init(self, context):
        vars = context['vars']
        #
        self._has_vimtex = None
        self._vimtex_maps = self._check_vimtexplugin()
        # Populate completion lists...
        self._make_lists()
        #
        if vars.get('deoplete#sources#latex#include_web_math',
                    self.debug_enabled):
            self._update_lists(self._packages['misc-web'], 'misc-web')
        #
        if vars.get('deoplete#sources#latex#include_misc',
                    self.debug_enabled):
            self._update_lists(self._packages['misc-other'], 'misc-other')
        #
        # Echo these context items to logger for debugging...
        self._context_watch_items = ("complete_position", "next_input",
                                     "input", "complete_str", "position")
        #
        # Patterns for "math" and "text" modes, respectively...
        self._mRE = re.compile(r"\\?\w*$|"
                               r"(?<=end\{)[^}]*$", re.IGNORECASE)
        #
        self._tRE = re.compile(r"\\?\w*$|"
                               r"(?<=\w\[)[^],]*$|"
                               r"(?<=\w,)[^],]*$|"
                               r"(?<=\S\{)[^}]*$", re.IGNORECASE)
        #
        # Pattern for `\documentclass` and `\usepackage` options.
        self._dcup_opt_RE = re.compile(r'^(?:.*)(\\\w+)'
                                       r'(?:.*)\[(?:[^]]*)?(?:]?{(.*)})')

    def get_complete_position(self, context):
        # Seems to mimic the "first-call" behavior of Vim's "complete-
        # functions", i.e. specifies start of completion.
        #
        # XXX - Simply searching for end instead is probably faster. See
        # deoplete-jedi, which uses something like this:
        #
        # >>> m = re.search(r'[{([,]$', context['input'])
        # >>> if m: return m.end()
        # >>> m = re.search(r'\\?\w+$', context['input'])
        #
        useRE = self._mRE if self._has_math(context["position"]) else self._tRE
        m = useRE.search(context["input"])
        return m.start() if m else -1

    def gather_candidates(self, context):
        # TODO - Devise some way to reproduce intermittent issue re truncated
        # suggestions in PUM.
        #
        self.debug_enabled and self._whine(
            "== Selected context items ==",
            *("{:12} : {!r}".format(*x) for x in context.items() if
              x[0] in self._context_watch_items),
            "{:12} : {!r}".format("synIDattr", list(
                self._check_synstack(context["position"]))),
            dequote=True)
        #
        cinput = context['input']
        nextin = context['next_input']
        #
        # Call vimtex omnifunc when appropriate.
        vt_clues = ('cite', 'ref', 'include', 'gls')
        if (self._has_vimtex and any(s in cinput.lower() for s in vt_clues) and
                self.vim.call('vimtex#complete#omnifunc', 1, '') >= 0):
            vimtex_cands = self.vim.call('vimtex#complete#omnifunc',
                                         0, context['complete_str'])
            if vimtex_cands:
                self.debug_enabled and self._whine(
                    'vimtex omni matches:', vimtex_cands)
                return vimtex_cands
        #
        # ``:help deoplete`` says:
        # >     Note: The source must not filter the candidates by user input.
        # >     It is |deoplete-filters| work.
        #
        # Does this apply to the following? Filters rank/sort candidates by
        # priority. This is just offering them up for consideration.
        #
        # Commands with kev/val pairs...
        opt_m = re.match(r'(\\\w+)', cinput)
        if opt_m and opt_m.group(1) in self._options:
            for opt, pat in self._options[opt_m.group(1)]['sigpats']:
                sig_m = re.match(pat, cinput)
                self.debug_enabled and self._whine(
                    'Trying keyval pat: %r' % pat)
                if sig_m and self._options[opt_m.group(1)][opt]:
                    return sorted((self._make_item(o, {}, 'options') for o in
                                   self._options[opt_m.group(1)][opt]),
                                  key=lambda i: i['word'].lower())
        # Options for `\documentclass` and `\usepackage`. For now, it only
        # populates after the main class/package argument has been provided.
        dcup_opt_m = self._dcup_opt_RE.match(cinput + nextin)
        if dcup_opt_m:
            back_cmd, embraced = dcup_opt_m.groups()
            self.debug_enabled and self._whine(
                "Opt match found - pack: %s, embr: %s" % (back_cmd, embraced))
            optout = []
            for packname, packdata in self._packages.items():
                opts = packdata.get('options', {}).get(back_cmd)
                if not opts:
                    continue
                if (embraced == packname or
                        self._class_names.get(embraced) == packname):
                    optout += opts
                    return sorted((self._make_item(o, {}, 'options', packname)
                                   for o in optout),
                                  key=lambda i: i['word'].lower())
        elif 'documentclass' in cinput:
            if re.match(r'^\s*\\documentclass(?:\[.*?\]s?)?{[^}]*$', cinput):
                return self._clss
        elif 'usepackage' in cinput:
            if re.match(r'^\s*\\usepackage(?:\[.*?\]\s?)?{[^}]*?$', cinput):
                return self._packs
        # This will be expanded if conditional completion based environment
        # context is ever implemented.
        elif cinput.strip() == '\\begin{' or cinput.strip() == '\\end{':
            return self._envs
        # Return the main commands lists.
        if self._has_math(context["position"]):
            return self._math
        else:
            return self._text

    def _find_packages(self):
        up_RE = re.compile(r'^\s*\\(usepackage|documentclass)'
                           r'(?:\[(.*?)\]\s?)?{([^}]+)}')
        for line in self.vim.current.buffer:
            if '\\begin{document}' in line:
                break
            m = up_RE.match(line)
            if m:
                yield (self._class_names[m.group(3)] if
                       'class' in m.group(1) else m.group(3)), m.group(2)

    def on_event(self, context):
        """Load packages on write.
        """
        # Using cwl "prefixed/long" form of class names, e.g., ``class-foo``,
        # to guard against collisions. XXX - verify reasoning because
        # readability suffers. Some packs, like "yathesis", define a "class"
        # as the dominant mode but the cwl filename doesn't reflect this...
        witgroups = dict(self._find_packages())
        witnessed = witgroups.keys()
        included = set.union(*(set(self._packages[p].get('includes', [])) for
                               p in witnessed if p in self._packages), set())
        available = (set(p['word'] for p in self._packs) |
                     set(self._class_names[c['word']] for c in self._clss))
        remainder = ((self._cats['packages'].keys() |
                      set(self._class_names.values())
                      ) - available - witnessed - included)
        if remainder:
            self.debug_enabled and self._whine(
                '"%r" removed, resetting...' % remainder)
            self._reset_lists()
            available = (set(p['word'] for p in self._packs) |
                         set(self._class_names.values()))
        for wit in witnessed & available:
            self.debug_enabled and self._whine(
                'Adding package: \'%s\'' % wit)
            self._update_lists(self._packages[wit], wit,
                               packargs=witgroups.get(wit))

    def _whine(self, *msg, dequote=False):
        """Echo debug spam to logger. See *deoplete#enable_logging()*
        for vimrc prerequisites.
        """
        if self.debug_enabled:
            if dequote is False:
                self.debug(json.dumps(msg, indent=2).strip('[]'))
            else:
                out = (''.join(''.join(l.rsplit('"', 1)).rstrip(',').split(
                    '"', 1)) for l in json.dumps(msg, indent=2).split('\n'))
                self.debug('\n'.join(out).strip('[]'))
        return None

    def _check_vimtexplugin(self):
        self._has_vimtex = True if self.vim.vars.get(
            'vimtex_imaps_enabled') else False
        rawlist = self.vim.vars.get(
            'vimtex_imaps_list') if self._has_vimtex else None
        return {item['rhs']: '`' + item['lhs']
                for item in rawlist} if rawlist else None

    def _make_optpats(self, opts, sigs):
        # Get all variations for known "usable" opts (currently only ``color``)
        known_opts = dict(keyvals=('keyval', 'key', '<%options%>'),
                          color=('color',))
        outpats = []
        subpat_RE = re.compile(r'(?:([(])(?:[^)]+?)([)]))|'
                               r'(?:(\[)(?:[^]]+?)(\]))|'
                               r'(?:({)(?:[^}]+?)(}))')
        if isinstance(sigs, str):
            sigs = [sigs]
        for opt in opts:
            tokens = known_opts.get(opt)
            if not tokens:
                continue
            for sig in sigs:
                try:
                    token = next(s for s in tokens if s in sig)
                except StopIteration:
                    continue
                tok_start = sig.rfind(token)
                last_brack = max(sig.rfind(c, 0, tok_start) for c in '[{(')
                pre_pat = sig[:last_brack]
                patted = subpat_RE.sub(r'(\s?[\1\3\5][^\2\4\6]+?[\2\4\6])?',
                                       repr(pre_pat).strip("'"))
                outpats.append((opt,
                                r'%s\s?[%s]' % (patted, sig[last_brack])))
        return outpats

    def _make_item(self, entname, entdata, catname, packname=None):
        # Get abbreviated category ("kind") name.
        kshrt = self._cat2kind[catname]
        ksing = self._plur2sing.setdefault(catname, catname.rstrip('s'))
        # All entries get one of these:
        complete_dct = {'kind': packname + ' ' + kshrt if packname else ksing,
                        'word': entname}
        if catname == 'options':
            lhs, _, rhs = entname.partition('#')
            if rhs:
                rhs = ' (' + rhs.replace(',', ', ') + ')'
                complete_dct.update(word=lhs, abbr=(lhs + rhs))
        # For now, use whatever sig comes first if more than one.
        try:
            sig = entdata.get('sig')
        except AttributeError:
            sig = None
        else:
            if sig:
                sig = sig[0] if hasattr(sig, '__setitem__') else sig
        # Check for argument-fields data under ``options`` in ``meta``.
        try:
            opts = entdata.get('meta', {}).get('options')
        except AttributeError:
            opts = None
        #
        if catname == 'commands':
            # Append vimtex hotkey mapping to symbol if available.
            if self._vimtex_maps and entname in self._vimtex_maps:
                vt = '\t(' + self._vimtex_maps[entname] + ')'
            else:
                vt = ''
            symbol = entdata['symbol'] + vt if entdata.get('symbol') else vt
            complete_dct.update(menu=symbol)
            # ``abbr`` is for display purposes only...
            if sig:
                complete_dct.update(abbr=sig)
            # Add args/options if present.
            if opts:
                # Create a fake/standin signature if none provided.
                if not entdata['sig']:
                    newsig = entname + ''.join('[%s]' % o for o in opts)
                    entdata.update(sig=newsig)
                    complete_dct.update(abbr=entdata['sig'])
                # Retrieve a list of (opt, pat) tuples.
                pats = self._make_optpats(opts.keys(), entdata['sig'])
                newopt = dict(sigpats=pats, **opts)
                # If an option's value is None, it's a "shared" option.
                # Arrange for these to be managed centrally.
                for optname, optargs in newopt.items():
                    if optname == 'sigpats' or optargs is not None:
                        continue
                    newargs = self._options['__shared'].setdefault(optname,
                                                                   set())
                    newopt.update({optname: newargs})
                self._options.update({entname: newopt})
        #
        if catname == 'environments' and sig:
            fields = sig.partition('}')[-1]
            if fields:
                complete_dct.update(abbr=(entname + ' ' + fields))
        try:
            # Some info values are tuples with multiple signatures.
            infostr = (entdata['info'] if
                       isinstance(entdata['info'], (str, type(None))) else
                       '\n'.join(entdata['info']))
        except (KeyError, TypeError):
            pass
        else:
            # Cannot be ``None``, otherwise "null" appears in preview window...
            if infostr:
                complete_dct.update(info=infostr)
        return complete_dct

    def _purge_lists(self, packname):
        if packname not in self._packages:
            return
        for included in self._packages[packname].get('includes', []):
            self._purge_lists(included)
        # "porc" as in "package" or "class"...
        for porc_list in (self._clss, self._packs):
            for porc in porc_list[:]:
                # Get "long" version of class name (cwl filename format)
                if porc_list is self._clss:
                    porcword = self._class_names[porc['word']]
                else:
                    porcword = porc['word']
                if porcword == packname:
                    # Remove the package from "available" (completions) list.
                    porc_list.remove(porc)

    def _update_lists(self, cats, packname=None, packargs=None):
        # Key for ``list.sort()`` below...
        def key(item):
            return item.get('word').lower()
        #
        for catname, catdata in cats.items():
            if not catdata or catname == 'info':
                continue
            if catname == 'includes':
                for pack in catdata:
                    if pack in self._packages:
                        self._update_lists(self._packages[pack], pack)
                continue
            for entname, entdata in catdata.items():
                complete_dct = self._make_item(entname, entdata,
                                               catname, packname)
                if catname == 'commands':
                    if 'math' in entdata['mode']:
                        self._math.append(complete_dct)
                        self._math.sort(key=key)
                    if 'text' in entdata['mode']:
                        self._text.append(complete_dct)
                        self._text.sort(key=key)
                elif catname == 'environments':
                    self._envs.append(complete_dct)
                    self._envs.sort(key=key)
                elif catname == 'packages':
                    self._packs.append(complete_dct)
                    self._packs.sort(key=key)
                elif catname == 'classes':
                    self._clss.append(complete_dct)
                    self._clss.sort(key=key)
        if not packname:
            return
        self._purge_lists(packname)
        # Currently, class options don't unlock any "shared" options.
        if not packargs or packname.startswith('class'):
            return
        po_pool = cats['options'].get('\\usepackage')
        if not po_pool:
            return
        for parg in packargs.split(','):
            parg_opts = po_pool.get(parg)
            if not parg_opts:
                continue
            for optname, optlist in parg_opts.items():
                if optlist:
                    optset = self._options['__shared'].get(optname)
                    optset |= set(optlist)

    def _reset_lists(self):
        (self._math, self._text, self._clss,
         self._envs, self._packs) = [], [], [], [], []
        self._options = {'__shared': {}}
        self._update_lists(self._cats)

    def _make_lists(self):
        """Make global lists conforming to the interface required by
        ``gather_candidates``. The entries here belonging to both
        math and text modes are few. Store all as a class attributes.
        """
        module_dir = os.path.dirname(__loader__.path)
        # This path is hard-coded, but likely won't change...
        fpath = os.path.join(module_dir, '../resources/latest.json')
        with open(fpath) as f:
            self._packages = json.load(f)
        packages = self._packages
        #
        # Lookups based on cwl filenames are unwieldy for classes, e.g.,
        # ``class-foo,bar``. Need crutch like ``{"foo": "class-foo,bar", ...}``
        class_names = (set.union(*({(short, long)} for short in
                                   long.partition('-')[-1].split(','))) for
                       long in packages if long.startswith('class'))
        self._class_names = dict(set.union(*class_names))
        #
        # Initialize base lists of completion items by category (kind).
        cats = self._cats = {}
        cats['classes'] = {short: {'info': packages[long].get('info')} for
                           short, long in self._class_names.items()}
        #
        cats['packages'] = {p: {'info': packages[p].get('info')} for p in
                            packages if not any(p.startswith(s) for s in
                                                ('class', 'misc', 'latex'))}
        #
        # Also add "base" defs from texstudio's ``completion`` directory. At
        # the time of this first commit, these are: 'latex-l2tabu',
        # 'latex-209', 'latex-dev', 'latex-mathsymbols', 'latex-document'
        cat_kinds = 'classes packages commands environments options'.split()
        cats.update(zip(cat_kinds[-3:], ({}, {}, {})))
        #
        for pname in packages:
            if not pname.startswith('latex'):
                continue
            for catname, catdata in packages[pname].items():
                if catname not in cats or not catdata:
                    continue
                # ``ent*`` as in "entry"...
                for entname, entdata in catdata.items():
                    cats[catname].update({entname: entdata})
        #
        self._plur2sing = {'classes': 'class'}
        self._cat2kind = dict(zip(cat_kinds, 'cls pkg cmd env opt'.split()))
        #
        self._reset_lists()

    def _check_synstack(self, position):
        """Ask Vim for syntax highlighting context...
        """
        return (self.vim.call('synIDattr', ID, 'name') for ID in
                self.vim.call('synstack', *position[1:3]))

    def _has_math(self, position):
        return any('math' in v.lower() for v in self._check_synstack(position))
