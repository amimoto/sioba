#!/usr/bin/sh


curl -sSL https://pdm-project.org/install-pdm.py | python3 -

echo "installing development script code"
cd /src

pdm install -d

