FROM ubuntu:24.04


ARG CONTAINER_UID=1000
ARG CONTAINER_GID=1000
ENV CONTAINER_UID=$CONTAINER_UID
ENV CONTAINER_GID=$CONTAINER_GID

ENV TZ="America/Vancouver"
ENV USER=user

RUN :\
    # Packages setup
    && apt update \
    # Make sure we're up to date
    && DEBIAN_FRONTEND=noninteractive apt dist-upgrade -y \
    # Super handy tools used typically for in-situ debugging
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        gnupg \
        iproute2 \
        iputils-ping \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        python3.12 \
        python3.12-dev \
        python3.12-venv \
        ssh \
        software-properties-common \
        sqlite3 \
        sudo \
        telnet \
        vim-nox \
        wget \
    # Install nodejs
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest typescript --unsafe-perm=true --allow-root \
    # Install yarn
    && npm install --global yarn \
    # Cleanup
    && apt clean \
    && rm -rf ~/.cache \
    && rm -rf /var/lib/apt/lists/* \
    # 24.04 now includes a default ubuntu user. We will remove it for our user
    && userdel -r ubuntu \
    # Create the new user
    && groupadd -f -g $CONTAINER_GID $USER \
    && useradd -ms /bin/bash -d /home/$USER -G sudo $USER -u $CONTAINER_UID -g $CONTAINER_GID \
    && mkdir /app \
    && chown -R $CONTAINER_UID:$CONTAINER_GID /app \
    && :

# Let's sit in the src directory by default
WORKDIR /src

USER $USER

# Copy over the data files
COPY --chown=$USER:$USER . /src

ENV PATH=/home/$USER/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN /src/docker/setup-env.sh

CMD sleep infinity

