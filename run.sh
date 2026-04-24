#!/usr/bin/env bash
#
# dictate — voice-to-clipboard via OpenAI Whisper.
#
# Wrapper that loads secrets and config, then invokes the Python script
# from its own directory. Safe to symlink into ~/.local/bin.

set -euo pipefail

# Resolve the real location of this script, following symlinks. This lets
# ~/.local/bin/dictate be a symlink to the checkout while still finding
# main.py relative to the real file.
SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname -- "$SCRIPT_PATH")"

# --- config ------------------------------------------------------------------

# Secrets live outside the repo. Load them from a file with mode 600.
# Create it with:
#   install -m 600 /dev/null ~/.config/dictate/env
#   $EDITOR ~/.config/dictate/env
ENV_FILE="${DICTATE_ENV_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/dictate/env}"

if [[ -f "$ENV_FILE" ]]; then
    # Refuse to read world-readable secrets files.
    perms="$(stat -c '%a' -- "$ENV_FILE" 2>/dev/null || echo 000)"
    if [[ "${perms: -2}" != "00" ]]; then
        printf 'dictate: refusing to load %s (mode %s, expected 600)\n' \
            "$ENV_FILE" "$perms" >&2
        exit 1
    fi
    set -o allexport
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +o allexport
fi

# Pick an interpreter: prefer a project venv, fall back to system python3.
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="$(command -v python3 || true)"
fi

if [[ -z "$PYTHON" ]]; then
    printf 'dictate: no python3 found\n' >&2
    exit 1
fi

# --- exec --------------------------------------------------------------------

# exec replaces this shell with Python — signals and exit code propagate cleanly.
exec "$PYTHON" "$SCRIPT_DIR/main.py" "$@"
