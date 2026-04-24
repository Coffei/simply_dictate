#!/usr/bin/env python3
"""
dictate: voice-to-clipboard via OpenAI Whisper, for Niri/Wayland.

Toggles recording on each invocation. Bind a single Niri key to this script.

System deps:
    parecord       (pulseaudio-utils — works through pipewire-pulse on Fedora)
    wl-copy        (wl-clipboard)
    notify-send    (libnotify, optional but nice)

Python deps:
    requests

Niri config (~/.config/niri/config.kdl):
    binds {
        Mod+V { spawn "dictate"; }
        Mod+Shift+V { spawn "dictate" "cancel"; }
    }

Env vars:
    OPENAI_API_KEY   required
    DICTATE_MODEL    default "gpt-4o-transcribe"
    DICTATE_LANGUAGE default "" (set to empty for auto-detect)
    DICTATE_PROMPT   vocabulary bias (≤ ~224 tokens / ~900 chars)
    DICTATE_API_URL  swap for Groq by setting to
                     https://api.groq.com/openai/v1/audio/transcriptions
                     (use DICTATE_MODEL=whisper-large-v3-turbo with Groq)
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------- config ----
API_KEY  = os.environ.get("OPENAI_API_KEY")
API_URL  = os.environ.get("DICTATE_API_URL",
                          "https://api.openai.com/v1/audio/transcriptions")
MODEL    = os.environ.get("DICTATE_MODEL", "gpt-4o-transcribe")
LANGUAGE = os.environ.get("DICTATE_LANGUAGE", "")
PROMPT   = os.environ.get("DICTATE_PROMPT",
    "Elixir, Phoenix, Ecto, Ecto.Multi, Dialyzer, OTP, BEAM, Flutter, "
    "FCM, APNs, OAuth, SAML, OIDC, Niri, Fedora, Helix, Neovim, LiveView, "
    "PostgreSQL, JSONB, GitLab CI, Ollama, Groq."
)

RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
STATE_DIR   = RUNTIME_DIR / "dictate"
STATE_DIR.mkdir(exist_ok=True)
PID_FILE    = STATE_DIR / "record.pid"
AUDIO_FILE  = STATE_DIR / "recording.wav"

MAX_WAIT_FOR_FILE_S = 3.0   # how long to wait for parecord to flush the WAV
REQUEST_TIMEOUT_S   = 60


# ---------------------------------------------------------------- helpers ---
def notify(title: str, body: str = "", urgency: str = "normal") -> None:
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-t", "2500",
             "-a", "dictate", title, body],
            check=False, timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # notifications are best-effort


def running_pid() -> int | None:
    """Return PID of the active parecord process, or None (cleaning up stale files)."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # existence probe
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return None


# --------------------------------------------------------------- actions ----
def start_recording() -> None:
    AUDIO_FILE.unlink(missing_ok=True)

    proc = subprocess.Popen(
        ["parecord", "--channels=1", "--rate=16000",
         "--file-format=wav", str(AUDIO_FILE)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,   # detach from our process group
    )
    PID_FILE.write_text(str(proc.pid))
    notify("🎙  Recording", "Press the bind again to stop")


def stop_and_transcribe() -> None:
    pid = running_pid()
    if pid is None:
        notify("Dictation", "Not recording", urgency="low")
        return

    # SIGINT lets parecord flush a valid WAV header; SIGTERM truncates.
    try:
        os.kill(pid, signal.SIGINT)
    except ProcessLookupError:
        pass
    PID_FILE.unlink(missing_ok=True)

    # Wait for parecord to finalize the file.
    deadline = time.monotonic() + MAX_WAIT_FOR_FILE_S
    while time.monotonic() < deadline:
        if AUDIO_FILE.exists() and AUDIO_FILE.stat().st_size > 1024:
            break
        time.sleep(0.05)
    else:
        notify("Dictation error", "No audio captured", urgency="critical")
        return

    if not API_KEY:
        notify("Dictation error", "OPENAI_API_KEY not set", urgency="critical")
        AUDIO_FILE.unlink(missing_ok=True)
        return

    notify("⏳  Transcribing", "", urgency="low")

    try:
        with AUDIO_FILE.open("rb") as f:
            data = {"model": MODEL, "response_format": "text"}
            if LANGUAGE:
                data["language"] = LANGUAGE
            if PROMPT:
                data["prompt"] = PROMPT

            resp = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {API_KEY}"},
                files={"file": (AUDIO_FILE.name, f, "audio/wav")},
                data=data,
                timeout=REQUEST_TIMEOUT_S,
            )
        resp.raise_for_status()
        text = resp.text.strip()
    except requests.HTTPError as e:
        body = (e.response.text or "")[:120]
        notify("Dictation error",
               f"HTTP {e.response.status_code}: {body}",
               urgency="critical")
        return
    except requests.RequestException as e:
        notify("Dictation error", f"Network: {e}", urgency="critical")
        return
    finally:
        AUDIO_FILE.unlink(missing_ok=True)

    if not text:
        notify("Dictation", "(empty transcription)", urgency="low")
        return

    try:
        subprocess.run(
            ["wl-copy"],
            input=text.encode("utf-8"),
            check=True, timeout=2,
        )
    except (FileNotFoundError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as e:
        notify("Dictation error", f"Clipboard failed: {e}", urgency="critical")
        return

    preview = text if len(text) <= 80 else text[:77] + "…"
    notify("📋  Copied", preview)


def cancel() -> None:
    pid = running_pid()
    if pid is None:
        notify("Dictation", "Nothing to cancel", urgency="low")
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    PID_FILE.unlink(missing_ok=True)
    AUDIO_FILE.unlink(missing_ok=True)
    notify("🗑  Cancelled", "", urgency="low")


# --------------------------------------------------------------- entry -----
def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "cancel":
        cancel()
        return

    if running_pid() is not None:
        stop_and_transcribe()
    else:
        start_recording()


if __name__ == "__main__":
    main()
