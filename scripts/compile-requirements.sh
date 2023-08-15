#!/bin/bash

set -euo pipefail

cd $(dirname $0)/..

pip-compile -q ./scripts/requirements.in "$@"
pip-compile -q ./scripts/requirements-dev.in "$@"
