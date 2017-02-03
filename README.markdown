deoplete-latex
==============

##Warning
This is not a serious [deoplete][1] source. It's merely a "dumb list" of LaTeX
commands thrown together ad hoc to assist the infrequent user or LaTeX novice.
To be clear, **there's no syntax analysis happening here**, no "intellisense"
engine humming in the background. (See [Poor performance](#poor-performance)
below.)

[1]: https://github.com/Shougo/deoplete.nvim


![screenshot](https://cloud.githubusercontent.com/assets/12665556/22585211/7d79bfe4-e9ab-11e6-81d6-258cd598e7ee.png)

##Features (or lack thereof)

* delegates to [vimtex][2] for *all* completion capabilities offered by the
  plugin (like `\cite{}`, `\ref{}`, etc.), meaning vimtex must be loaded for
  these to be available

* completion offerings are LaTeX only; no ConTeXt, Texinfo, etc.

* packages listed in TeXstudio's `.cwl` [repo][3] are included as default
  sources; currently, these are not extensible, (you can't add your own local
  `.cwl` header), though this could change

* key/value args and other command options noted in TeXstudio's [cwl spec][4]
  tend to work as expected

* all preview-window doc strings were removed in favor simple signatures; see
  [vim-latexrefman][5] for full docs integration.

* in-menu Unicode symbols for relevant commands

* package contents loaded on save; previous attempts at dynamic loading have
  been abandoned, for now

[2]: https://github.com/lervag/vimtex
[3]: https://sourceforge.net/p/texstudio/hg/ci/default/tree/completion/
[4]: http://texstudio.sourceforge.net/manual/current/usermanual_en.html#CWLDESCRIPTION
[5]: https://github.com/poppyschmo/vim-latexrefman


##Global options
```vim
" Include macros like `\ihat` from MathJax and KaTeX.
let g:deoplete#sources#latex#include_web_math = 1  " default 0

" Include 'other' miscellaneous commands, environments, options...
let g:deoplete#sources#latex#include_misc = 1      " default 0
```

##Issues

There are far too many niggling issues to list here (and likely some major
unknown unknowns, as well). Most can safely be attributed to the author's
overall lack of computer knowhow. (See `dev` branch for build scripts.)

### Poor performance
When editing documents longer than a few pages, especially ones dependent on
more than a few packages, initial completion suggestions are truncated
(seemingly arbitrarily). This is accompanied by laggy cursor movement and
jittery scrolling. Things settle down after a minute or so, but this is
obviously a deal breaker for non-trivial work and stands as the foremost
impediment to this becoming a valid deoplete source.

### No context awareness re "environment"
Some commands are only supported in a given environment. These constraints
currently go unheeded.

### Wrong "mode" context
Many commands are tagged with the wrong combination of text/math labels,
preventing them from showing up for completion in a given mode. Absent a
more precise and authoritative source for such data, this won't change.

### Missing options
Much like the "mode" issue, most of these are attributable to incomplete or
erroneous source information, mainly because TeXstudio's cwl roster is
crowd-sourced and imperfect. Unless some facility for extensibility is
implemented here, this also won't change.


