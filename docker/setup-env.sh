#!/usr/bin/sh

# Set up environment variables for `nvm`
export NVM_DIR="/home/user/.nvm"
export PATH="$NVM_DIR/versions/node/v18.18.2/bin:$PATH"
export PATH="/home/user/.local/bin:$PATH"

echo "USER IS $USER"

# Install `nvm` and use it to install Node.js, npm, and TypeScript
echo "Installing NVM"
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
. "$NVM_DIR/nvm.sh"

nvm install stable

nvm alias default stable

npm install -g typescript

npm install -g npm@latest

echo "Installing PDM"
curl -sSL https://pdm-project.org/install-pdm.py | python3 -

echo "installing development script code"
cd /src

pdm install -d

