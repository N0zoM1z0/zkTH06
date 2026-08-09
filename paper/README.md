# zkTH06 paper

This directory contains the living English LaTeX paper for zkTH06. It records
both the current method and the changes in research direction, including
discarded or narrowed claims.

Build from this directory with:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Remove generated files with `latexmk -C`. Generated PDF and LaTeX auxiliary
files are not tracked. Experimental numbers should only be promoted from local
notes into the paper when the command, input hash and evidence boundary are
recorded.
