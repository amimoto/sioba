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
        unzip \
        # For selenium testing
        chromium-driver \
        libnss3 \
        libatk1.0-0t64 \
        libatk-bridge2.0-0t64 \
        libcups2t64 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libxkbcommon0 \
        libxcb1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2t64 \
    # Install chromium
    # Pulled from here: https://vikyd.github.io/download-chromium-history-version/#/
    && wget "https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F1231300%2Fchrome-linux.zip?generation=1701355787197325&alt=media" -O /tmp/chromium.zip \
    && unzip /tmp/chromium.zip -d /opt \
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

