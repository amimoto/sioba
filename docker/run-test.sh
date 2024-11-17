#!/bin/bash

# Go into the project's source dir
cd /src

# Make sure we have the required modules installed
pdm install -d

# Wait till our nexus server is up and running
# before attempting any tests
pdm run python ./docker/wait-for-nexus.py

# Then run the nox test scripts
pdm run nox --reuse-existing-virtualenvs $@

