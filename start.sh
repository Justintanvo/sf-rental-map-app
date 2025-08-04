#!/bin/sh
set -e

python3 -m pip install -r requirements.txt
python3 -m gunicorn app:server --timeout 120 --bind 0.0.0.0:8080