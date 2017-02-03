
LISTS := lists
DATA := data
KWIKI := $(DATA)/KaTeX.wiki
LSHORT := $(DATA)/lshort
AMSHELP := $(DATA)/amshelp
AMSMATH := $(DATA)/amsmath
UNIMATH := $(DATA)/unimath
CWL := $(DATA)/texstudio/completion
NMODS := node_modules
LATEST := union_cwl.json


# These two sources from CTAN cannot be pinned and may become inaccessible at
# any time. When that happens, their recipes below will fail...
AMSHELP_REV := 'February 12, 2011'
AMSLDOC_REV := 2016-11-14

# Pinned sources and URLs -----------------------------------------------------
KWIKI_REV := 936af76133a0049d345effc0b2fff23574332a2c
LSHORT_REV := 5.06
LSHORT_URL := https://tobi.oetiker.ch/lshort/lshort-$(LSHORT_REV).src.tar.gz
TSCWL_REV := 89b651aae5cf74f66dc3a183679706841b9bc994
REFMAN_REV := 557
REFMAN_QUERY := '?revision='$(REFMAN_REV)'&content-type=text%2Fplain'
REFMAN_BASEURL := 'http://svn.gna.org/viewcvs/*checkout*/latexrefman/trunk/latex2e.texi'
REFMAN_URL := $(REFMAN_BASEURL)$(REFMAN_QUERY)
# -----------------------------------------------------------------------------

# Always use "discovered" pathnames.
GPATH = $(LISTS)

vpath %.json $(LISTS)
vpath %.md $(KWIKI)
vpath %.idx $(LSHORT):$(AMSMATH)
vpath %.tex $(LSHORT):$(AMSHELP):$(AMSMATH):$(UNIMATH)
vpath %.texi $(DATA)
vpath %.info $(DATA)
vpath %.zip $(DATA)
vpath %.src.tar.gz $(DATA)
vpath %.cwl $(CWL)

lsrc := $(notdir $(wildcard $(DATA)/lshort-*.src.tar.gz))
ifeq ($(lsrc),)
	lsrc := _fetch_lshsrc_tar
endif


latest.json: $(LATEST)
	./compact_json.py $< $@

union_cwl.json union_mj_refman.json: update_mathjax.json refman_idx.json unimath.json \
					texstudio_cwl.json
	python3 meld_mj_refman.py

texstudio_cwl.json: latex-document.cwl | $(LISTS)
	python3 get_cwl.py

unimath.json: unicode-math-table.tex | $(LISTS)
	python3 get_unimath.py

refman_idx.json: latex2e.info latex2e.texi | $(LISTS)
	python3 get_refman.py

update_mathjax.json: update_asm_mj.json
	node update_mathjax.js

update_asm_mj.json: union_katex_lshort.json | $(NMODS)
	node update_asm_mj.js

union_katex_lshort.json: katex_symbols.json katex_wiki.json lshort_idx.json \
				amshelp_template.json amsmath.json
	python3 meld_katex_lshort.py

amshelp_template.json: template.tex
	cd data/amshelp && \
		grep -i 'version\s.\+'$(AMSHELP_REV) template.tex || \
		{ echo 'Wrong revision date for "template.tex"' >&2 && exit 1; }

amsmath.json: amsldoc.idx template.tex | $(LISTS)
	python3 get_amsmath.py

lshort_idx.json: lshort.idx | $(LISTS)
	python3 get_lshort.py

katex_wiki.json: Function-Support-in-KaTeX.md | $(LISTS)
	python3 get_katex_wiki.py

katex_symbols.json: | $(LISTS)
	python3 get_katex_symbols.py

latex-document.cwl: | $(CWL)

latex2e.info: latex2e.texi | $(DATA)
	cd data && \
		makeinfo --no-split $(<F)

latex2e.texi: | $(DATA)
	cd data && \
		curl -Lo $@ $(REFMAN_URL)

unicode-math-table.tex: | $(DATA)
	cd data && \
		curl -LO http://mirrors.ctan.org/macros/latex/contrib/unicode-math.zip && \
		unzip unicode-math.zip && \
		mv unicode-math unimath

lshort.idx: lshort.tex
	cd $(LSHORT) && \
		latexmk lshort.tex

template.tex: | $(DATA)
	cd data && \
		curl -LO http://mirrors.ctan.org/info/amslatex/primer.zip && \
		unzip primer.zip && \
		mv primer amshelp

# Includes crude revision check (see header).
amsldoc.idx: | $(AMSMATH)
	cd $(AMSMATH) && \
		grep 'revised\s[[:digit:]-]\{10\},\s'$(AMSLDOC_REV) amsldoc.tex || \
		{ echo 'Wrong revision date for "amsldoc.tex"' >&2 && exit 1; }
	cd $(AMSMATH) && \
		latexmk amsldoc.tex

lshort.tex: | $(LSHORT)

Function-Support-in-KaTeX.md: | $(KWIKI)
	cd $(KWIKI) && \
		git checkout $(KWIKI_REV)

$(AMSMATH): | $(DATA)
	cd data && \
		curl -LO https://www.ctan.org/tex-archive/macros/latex/required/amsmath.zip && \
		unzip amsmath.zip

$(CWL): | $(DATA)
	cd data && \
		hg clone http://hg.code.sf.net/p/texstudio/hg/ texstudio
	cd $(CWL) && \
		hg update $(TSCWL_REV)

# Tarball not under VC, so extracting subdir is cruft-free vis-a-vis linking.
$(LSHORT): | $(DATA)
	cd data && \
		curl -LO $(LSHORT_URL) && \
		tar -xvf lshort-$(LSHORT_REV).src.tar.gz && \
		mv lshort-$(LSHORT_REV)/src lshort && \
		rm -rf lshort-$(LSHORT_REV)

$(KWIKI): | $(DATA)
	git clone https://github.com/Khan/KaTeX.wiki.git $@

$(DATA):
	mkdir -v $@

$(LISTS):
	mkdir -v $@

$(NMODS):
	npm install

.DELETE_ON_ERROR:

# vim:list
