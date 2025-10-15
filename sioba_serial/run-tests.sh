#!/bin/bash

uv run pytest --cov=sioba_serial --cov-report=html $@
