#!/bin/bash

uv run pytest --cov=sioba_nicegui --cov-report=html $@
