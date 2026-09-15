# Opti

**Opti** is a lightweight Windows tray app that transforms text in place — prompts, messages, summaries, and key extractions — summoned with a global hotkey, Spotlight-style.

Tagline: *Prompt & text transformer*

**Default provider:** Google Gemini 3.5 Flash (free-tier friendly). Switch to Groq, OpenRouter, Anthropic, or OpenAI in Settings.

## Features

- Global hotkey pill UI (collapse to floating chip)
- Transform modes: Optimize prompt, Polish message, Summarize, Extract (80/20), Ask
- Project context profiles with per-project default transform
- Voice input (optional, local Whisper)
- Auto-inject into previous window (opt-in)
- History, privacy mode, configurable shortcuts

## Requirements (development)

- Windows 10/11
- Python 3.11+
- API key from your chosen provider ([Google AI Studio](https://aistudio.google.com/apikey) for Gemini)

## Install (from source)

```powershell
git clone https://github.com/Pingwyd/opti.git
cd opti
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Copy `config.example.json` to `config.json` or enter your API key on first launch.

Optional voice input:

```powershell
pip install -r requirements-voice.txt
```

Then enable **Settings → Privacy → Voice input**. The first run downloads the Whisper model (~150MB for `base`). Use the mic button on the prompt bar, or hold **Ctrl+Space** (default) while the popup is focused. Configure recording mode, model size, and shortcut under **Privacy** and **Shortcuts**.

## Download (releases)

GitHub Actions **Build & Release** runs on pull requests (tests + artifacts only) and publishes a GitHub Release when changes land on **`main`** (or when you push a `v*` tag).

| Artifact | Description |
|----------|-------------|
| **Opti-Setup-x.x.x.exe** | Windows installer (Inno Setup) — data in `%LOCALAPPDATA%\Opti` |
| **Opti-portable.zip** | Unzip and run `Opti.exe` — config/logs beside the exe (`portable.txt` marker) |

**Ship a release:** bump `APP_VERSION` in `brand.py`, update `CHANGELOG.md`, merge to `main`. CI tags `vX.Y.Z` from that version and uploads the installer + portable zip.

Optional manual tag (same version as `brand.py`):

```powershell
git tag v1.1.0
git push origin v1.1.0
```

Dry-run build only: **Actions → Build & Release → Run workflow** (no release on manual runs unless you push to `main` or a tag).

## Build locally

```powershell
pip install -r requirements.txt -r requirements-build.txt
pyinstaller packaging/opti.spec --noconfirm --clean
# Portable zip: dist\Opti\
# Installer: install Inno Setup 6, then compile packaging\installer.iss
```

## Configuration

Settings → tabs for General, Models, Privacy, Shortcuts, Startup, Projects.

Each provider can have its own API key. Keys are encrypted with **DPAPI** in `vault.json` (`dpapi:...`); `config.json` holds non-sensitive settings only. Switching provider in Settings loads that provider's saved key automatically.

**Installed app** stores data in `%LOCALAPPDATA%\Opti\` (`config.json`, `vault.json`, history, drafts)  
**Portable build** stores data next to `Opti.exe`

Never commit `config.json` or `vault.json` with real keys.

## Tests

```powershell
pytest tests/ -q
```

## Tray menu

Open Opti · Reset window position · Open history · Settings · Start with Windows · Quit

## License

MIT (add license file if publishing)
