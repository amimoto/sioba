#!/bin/bash

uv run pytest --cov=sioba --cov-report=html $@
