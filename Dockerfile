FROM registry.izaber.com/devops/base-docker-images/ubuntu:24.04

# Make the src directory
USER root
RUN mkdir /src && chown -R zaber: /src
USER zaber

# Let's sit in the src directory by default
WORKDIR /src

USER root

RUN apt update \
    && apt install -y \
            software-properties-common \
            build-essential \
            curl \
            git \
            gnupg \
            libssl-dev \
            libxml2-dev \
            libxslt1-dev \
            python3.12 \
            python3.12-dev \
            python3.12-venv \
            sqlite3 \
            telnet \
            vim-nox \
    # Install nodejs
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest typescript --unsafe-perm=true --allow-root \
    # Install yarn
    && npm install --global yarn
    # Cleanup extra files
    && apt clean \
    && rm -rf ~/.cache \
    && rm -rf /var/lib/apt/lists/*

USER zaber

# Copy over the data files
COPY --chown=zaber:zaber . /src

ENV PATH=/home/zaber/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN /src/docker/setup-env.sh

CMD sleep infinity

