# Masters-Thesis Template

Based on the [Master Thesis of Maximilian
Heisinger](https://epub.jku.at/obvulihs/content/titleinfo/6753610) and the [JKU
template](https://help.jku.at/kommunikation/de/sonstige-vorlagen/latex-und-open-office-vorlagen).

## Usage

Run `make` in the main directory to generate all embedded targets. Look for
TODOs in the document (e.g. by grepping for TODO, with `grep TODO \*\*.tex`).
Start with [thesis/main.tex](thesis/main.tex).

It is also recommended to add new targets to the `Makefile`, if the process to
build a thesis requires some figures to be rendered.

## Dependencies

Just install `texlive-full` from your package manager and add `rubber` for
compiling the document including all references.

In Ubuntu (>= 20.04), Mint, etc., just enter:

    sudo apt install texlive-full biber rubber

Arch Linux:

    sudo pacman -S texlive-most texlive-fontsextra biber rubber

## Issues with older Distributions of TexLive

Older TexLive (<2019) may have issues with compiling this thesis template. To
still enable these systems, an easy docker container was integrated into the
`Makefile`. Please [install docker](https://docs.docker.com/get-docker/)
according to your system's needs. This should then also work without issues in
Windows and macOS. In Ubuntu 20.04, the package should be called `docker.io`.
On older Ubuntu versions it gets more complicated, as an additional repository
is required, see [the
tutorial](https://docs.docker.com/engine/install/ubuntu/). To then use the
`Makefile` in "Docker-Mode", provide `DOCKERIZE=1` to make. A call looks like
that:

    make DOCKERIZE=1

If the container should be forced to be rebuilt, remove the
`.sai-thesis-distro` file that blocks the container from being rebuilt with
every call.
