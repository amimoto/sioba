#!/bin/bash

pdm run pytest --cov=sioba --cov-report=html $@
