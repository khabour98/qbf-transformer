FROM ubuntu:20.04

WORKDIR /mnt

RUN apt-get update
RUN TZ="Europe/Vienna" DEBIAN_FRONTEND="noninteractive" apt-get --no-install-recommends install texlive-latex-extra \
    texlive-lang-cyrillic \
    texlive-fonts-extra \
    biber rubber make \
    python3-pygments \
    texlive-lang-german \
    texlive-science \
    texlive-bibtex-extra \
    texlive-plain-generic -y

ARG UNAME=sai
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID -o $UNAME
RUN useradd -m -u $UID -g $GID -o -s /bin/bash $UNAME
USER $UNAME

RUN TZ="Europe/Vienna" DEBIAN_FRONTEND="noninteractive" mktexpk --mfmode / --bdpi 600 --mag 1+23/600 --dpi 623 ecss1095; \
    mktexpk --mfmode / --bdpi 600 --mag 1+23/600 --dpi 623 ecss1440; \
    mktexpk --mfmode / --bdpi 600 --mag 1+23/600 --dpi 623 ecss0800; \
    mktexpk --mfmode / --bdpi 600 --mag 1+23/600 --dpi 623 ecss1000; \
    mktexpk --mfmode / --bdpi 600 --mag 1+23/600 --dpi 623 ecsx1000; \
    mktexpk --mfmode / --bdpi 600 --mag 1+23/600 --dpi 623 ecss0900; \
    mktextfm larm1095; \
    mktexmf larm1095

ENTRYPOINT [ "/bin/bash", "-l", "-c" ]
