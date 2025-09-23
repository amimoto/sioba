#!/bin/bash

uv run pytest --cov=sioba_websocket --cov-report=html $@
