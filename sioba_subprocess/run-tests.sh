#!/bin/bash

uv run pytest --cov=sioba_subprocess --cov-report=html $@
