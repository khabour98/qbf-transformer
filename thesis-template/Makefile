# Very cool idea with dependency detection inside of a makefile taken from:
# https://stackoverflow.com/a/25668869
EXECUTABLES = rubber pdflatex biber
K := $(foreach exec,$(EXECUTABLES),\
        $(if $(shell which $(exec)),some string,$(error "No $(exec) in PATH! Install it (available in standard repos - see readme)")))

TEXFILES=$(wildcard thesis/*.tex thesis/chapters/*.tex thesis/cover/*.tex)

DOCKERCONTAINER?=sai-thesis-distro
DOCKERCALL=

ifdef DOCKERIZE
	CURRENT_UID := $(shell id -u)
	CURRENT_GID := $(shell id -g)

	DOCKERDEPEND=.$(DOCKERCONTAINER)
	DOCKERCALL=docker run -it -v $(CURDIR):/mnt --user $(CURRENT_UID):$(CURRENT_GID) --entrypoint bash $(DOCKERCONTAINER) -c "
	DOCKERCALL_END="
endif

all: thesis/main.pdf

thesis/main.pdf: $(TEXFILES) $(DOCKERDEPEND) ## Build the thesis.pdf
	$(DOCKERCALL) cd thesis; rubber --synctex --unsafe --pdf main.tex $(DOCKERCALL_END)

clean: $(DOCKERDEPEND)
	$(DOCKERCALL) cd thesis; rubber --synctex --unsafe --clean main.tex $(DOCKERCALL_END)
	rm -f thesis/main.pdf

$(DOCKERDEPEND): Dockerfile
	docker build --build-arg UID=$(CURRENT_UID) --build-arg GID=$(CURRENT_GID) -t $(DOCKERCONTAINER) .
	touch $(DOCKERDEPEND)
