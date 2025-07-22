#!/bin/bash

set -euo pipefail

cd $(dirname $0)

pip-compile -q requirements.in "$@"
pip-compile -q requirements-dev.in "$@"
