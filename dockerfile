FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV USER=buildozer
ENV HOME=/home/buildozer

# Dépendances système nécessaires à python-for-android
RUN apt-get update && apt-get install -y \
    python3 python3-dev python3-venv python3-pip \
    git zip unzip openjdk-17-jdk \
    autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev \
    cmake libffi-dev libssl-dev build-essential \
    ccache sudo \
    libltdl-dev \
    && rm -rf /var/lib/apt/lists/*

# Python packages stables
RUN pip3 install --no-cache-dir --upgrade pip \
 && pip3 install --no-cache-dir \
    "cython==0.29.36" \
    "pyjnius==1.4.2" \
    "buildozer==1.5.0" \
    appdirs packaging colorama jinja2 toml build

# Créer utilisateur non-root
RUN useradd -m -s /bin/bash $USER \
 && echo "$USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Préparer les dossiers de cache
RUN mkdir -p /home/buildozer/.buildozer \
 && mkdir -p /home/buildozer/.gradle \
 && chown -R buildozer:buildozer /home/buildozer

USER buildozer
WORKDIR /home/buildozer/app

# Accélération compilation
ENV USE_CCACHE=1
ENV PATH="/usr/lib/ccache:$PATH"

# Commande par défaut
CMD ["buildozer", "-v", "android", "debug"]