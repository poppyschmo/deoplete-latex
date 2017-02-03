Ignore this directory
=====================

These scripts are ephemeral and were only ever meant to work on the pinned
revisions listed in the makefile. They were created to generate `latest.json`
adhoc by scraping source code and documentation. Such material, by nature, has
no reliable interface. The date of the last commit to touch this directory
can be considered its sell-by.

## Requirements:
- `curl`, `tar`, `unzip`
- `hg`, `git`
- `latexmk`
- `makeinfo`
- `node` (version 6 or above)
- `python3`
- `texlive` (or equivalent)


## Building lshort

`lshort.idx` is an intermediate "build dependency" of the `lshort` book.
These are generated during the build process and not contained in the
`*.src.tar.gz` archive. Nor are they included in the various OS distribution
packages (e.g., `tex-lang-english` on Debian). More info on the build
requirements is available at [ctan] [1].


## Corner case example w. Fedora 24
This assumes all TeX packages from `sagemath` are already installed:
```
    # dnf install \
        texlive-cbfonts  \
        texlive-lgreek   \
        texlive-xypic    \
        texlive-IEEEtran \
        texlive-lastpage \
        texlive-greek-fo \
        texlive-polyglos \
        texlive-babel-gr \
        texlive-babel-ge \
        texlive-babel-fr \
        texlive-numprint
```
[1]: http://www.ctan.org/tex-archive/info/lshort/english
