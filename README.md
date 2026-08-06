# Opti

**Opti** is a lightweight Windows tray app that refines rough AI prompts into clear, well-engineered ones — summoned with a global hotkey, Spotlight-style.

Tagline: *Prompt refiner*

**Default provider:** Google Gemini 3.5 Flash (free-tier friendly). Switch to Groq, OpenRouter, or Anthropic in Settings.

## Features

- Global hotkey pill UI (collapse to floating chip)
- Project context profiles
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

## Download (releases)

GitHub Actions builds on every `v*` tag:

| Artifact | Description |
|----------|-------------|
| **Opti-Setup-x.x.x.exe** | Windows installer (Inno Setup) — data in `%LOCALAPPDATA%\Opti` |
| **Opti-portable.zip** | Unzip and run `Opti.exe` — config/logs beside the exe (`portable.txt` marker) |

Trigger a build manually: **Actions → Build & Release → Run workflow**, or push a tag:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

## Build locally

```powershell
pip install -r requirements.txt -r requirements-build.txt
pyinstaller packaging/opti.spec --noconfirm --clean
# Portable zip: dist\Opti\
# Installer: install Inno Setup 6, then compile packaging\installer.iss
```

## Configuration

Settings → tabs for General, Models, Privacy, Shortcuts, Startup, Projects.

On Windows, API keys are encrypted with **DPAPI** in `config.json` (`dpapi:...`).

**Installed app** stores data in `%LOCALAPPDATA%\Opti\`  
**Portable build** stores data next to `Opti.exe`

Never commit `config.json` with real keys.

## Tests

```powershell
pytest tests/ -q
```

## Tray menu

Open Opti · Reset window position · Open history · Settings · Start with Windows · Quit

## License

MIT (add license file if publishing)
