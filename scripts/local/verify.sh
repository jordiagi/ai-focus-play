#!/usr/bin/env bash
# Adversarial defect probes. See scripts/local/verify.py for what each one catches.
#   bash scripts/local/verify.sh [d1 d3 ...|all]
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
exec "$REPO_ROOT/backend/.venv/bin/python" "$SCRIPTS_DIR/local/verify.py" "$@"
