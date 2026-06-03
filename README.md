# SimplyDictate

Voice-to-clipboard dictation via OpenAI Whisper (or any compatible transcription
API), built for [Niri](https://github.com/YaLTeR/niri) (or similar WMs) and Wayland.

Bind a single key to toggle recording: press once to start, press again to stop.
The audio is transcribed and the text lands on your clipboard, ready to paste.
A second binding cancels an in-progress recording. If music is playing, it is
paused while you record and resumed afterwards.

## How it works

- Recording toggles on each invocation, tracked via a PID file in
  `$XDG_RUNTIME_DIR/dictate/`.
- Audio is captured with `parecord` (mono, 16 kHz WAV).
- On stop, the WAV is POSTed to the transcription API and the result is piped
  into `wl-copy`.
- Desktop notifications report state (recording, transcribing, copied, errors).

## Requirements

System dependencies:

| Tool          | Package              | Purpose                                  |
|---------------|----------------------|------------------------------------------|
| `parecord`    | `pulseaudio-utils`   | Audio capture (works via pipewire-pulse) |
| `wl-copy`     | `wl-clipboard`       | Copy to the Wayland clipboard            |
| `notify-send` | `libnotify`          | Desktop notifications (optional)         |
| `playerctl`   | `playerctl`          | Auto-pause/resume media (optional)       |

Python dependency: [`requests`](https://pypi.org/project/requests/).

## Installation

```sh
git clone https://github.com/Coffei/simply_dictate.git ~/.local/share/dictate
ln -s ~/.local/share/dictate/run.sh ~/.local/bin/dictate
```

Create a secrets file (mode `600`, kept outside the repo) with your API key:

```sh
mkdir -p ~/.config/dictate
install -m 600 /dev/null ~/.config/dictate/env
$EDITOR ~/.config/dictate/env
```

```sh
# ~/.config/dictate/env
OPENAI_API_KEY=sk-...
```

`run.sh` refuses to load this file unless it is mode `600`. It also prefers a
project virtualenv at `.venv/` if present, otherwise falls back to system
`python3`.

## Niri binding

In `~/.config/niri/config.kdl`:

```kdl
binds {
    Mod+V       { spawn "dictate"; }
    Mod+Shift+V { spawn "dictate" "cancel"; }
}
```

## Configuration

All configuration is via environment variables (set them in
`~/.config/dictate/env`):

| Variable            | Default                          | Description                                                        |
|---------------------|----------------------------------|--------------------------------------------------------------------|
| `OPENAI_API_KEY`    | _(required)_                     | API key for the transcription service.                             |
| `DICTATE_MODEL`     | `gpt-4o-transcribe`              | Transcription model.                                               |
| `DICTATE_LANGUAGE`  | `""`                             | ISO language code; empty enables auto-detect.                      |
| `DICTATE_PROMPT`    | _(tech vocabulary)_              | Vocabulary bias (≤ ~224 tokens / ~900 chars).                      |
| `DICTATE_API_URL`   | OpenAI transcriptions endpoint   | Override to use a compatible API (see below).                      |
| `DICTATE_KEEP_AUDIO`| _(unset)_                        | Set to `1`/`true`/`yes` to save timestamped recordings for debug.  |
| `DICTATE_ENV_FILE`  | `~/.config/dictate/env`          | Override the secrets file location.                                |

### Using Groq instead of OpenAI

```sh
DICTATE_API_URL=https://api.groq.com/openai/v1/audio/transcriptions
DICTATE_MODEL=whisper-large-v3-turbo
```

## License

[MIT](LICENSE)
