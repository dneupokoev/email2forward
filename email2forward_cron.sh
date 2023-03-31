#!/bin/bash
cd /opt/dix/email2forward/
PATH="/opt/dix/email2forward/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
VIRTUAL_ENV="/opt/dix/email2forward/.venv"

pipenv run python3 email2forward.py
