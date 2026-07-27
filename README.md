# MetaPrompt

Lightweight Windows tray app that rewrites rough AI prompts into well-engineered ones via a global hotkey — Spotlight-style, single-purpose.

**Default provider:** Google Gemini 3.5 Flash (free-tier friendly). You can switch to Groq, OpenRouter, or Anthropic via `config.json`.

## Requirements

- Windows 10/11
- Python 3.11+
- An API key for your chosen provider (Gemini recommended for $0 personal use: [Google AI Studio](https://aistudio.google.com/apikey))

The popup UI uses **PyQt6** (native Qt widgets). PyQt6 is heavier than a webview shell but gives precise control over the frameless pill bar, shadows, and drag behavior without nested browser chrome.

## Install

```powershell
cd metaprompt
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configure

1. Copy the example config (optional — a `config.json` is created automatically on first run):

```powershell
copy config.example.json config.json
```

2. Set your API key in one of these ways:

- Paste it when MetaPrompt prompts you on first launch, **or**
- Edit `config.json` and set `"api_key": "..."`, **or**
- Set the env var for your provider: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, or `ANTHROPIC_API_KEY`

Never commit `config.json` if it contains a real key.

On Windows, API keys saved via the app or migrated from plaintext are encrypted with **DPAPI** (user-scoped) and stored in `config.json` as `dpapi:<base64>`. Only your Windows user account can decrypt them.

### Provider switch

In `config.json`, set `"provider"` to one of:

| Provider | Notes | Default thorough / fast models |
|----------|--------|--------------------------------|
| `gemini` (default) | Best free-tier option for this use case | `gemini-3.5-flash` / `gemini-3.1-flash-lite` |
| `groq` | Very fast Llama via OpenAI-compatible API | `llama-3.3-70b-versatile` / `llama-3.1-8b-instant` |
| `openrouter` | One key, many free models | free Gemini / Llama IDs |
| `anthropic` | Paid (occasional trial credits only) | `claude-sonnet-5` / `claude-haiku-4-5` |

Changing `provider` and restarting is enough if you also set matching `model` / `model_fast` (or call `set_provider()` which applies presets). Example Groq:

```json
{
  "provider": "groq",
  "api_key": "gsk_...",
  "model": "llama-3.3-70b-versatile",
  "model_fast": "llama-3.1-8b-instant"
}
```

**Privacy note:** Gemini’s free tier may use prompts to improve Google’s products — don’t paste confidential material through it.

### Other `config.json` fields

| Key | Default | Meaning |
|-----|---------|---------|
| `provider` | `gemini` | Which backend `api.py` calls |
| `api_key` | `""` | Provider API key |
| `hotkey` | `ctrl+shift+space` | Global hotkey |
| `model` | (per provider) | Thorough mode model |
| `model_fast` | (per provider) | Fast mode model |
| `mode` | `thorough` | `thorough` or `fast` |
| `history_limit` | `50` | Max saved input/output pairs |
| `save_history` | `true` | When `false`, optimizations are not written to history |
| `exclude_sensitive` | `false` | When `true`, skip saves when the prompt matches sensitive patterns |
| `exclude_sensitive_keywords` | `[]` | Custom patterns (substring or regex); defaults apply when list is empty |
| `start_with_windows` | `false` | Launch MetaPrompt when Windows starts |
| `persist_draft` | `true` | Restore unsent prompt text from `draft.json` on reopen |

## History panel and privacy

Tray menu → **Open history** opens a searchable history browser (not the raw JSON file).

- **Search** filters prompts and results (debounced).
- **Date range** narrows to the last 7, 30, or 90 days.
- Click a row to view the full input and optimized output.
- **Use prompt** / **Use both** / **Re-run optimization** send the selection back to the main window.
- **Export JSON** saves `history.json` for backup or inspection.

Privacy controls:

| Control | Where | Effect |
|---------|--------|--------|
| **Save optimization history** | History dialog | Master toggle (`save_history` in config) |
| **Don't save prompts containing sensitive patterns** | History dialog | Skips saves when the prompt matches keywords (`exclude_sensitive`) |
| **Private** checkbox | Main popup (pill bar) | Skips history for that single submission |

History is stored only in local `history.json` — nothing is synced to a cloud backend.

## Draft persistence

If you type in the input bar and close, background, or quit the app before optimizing, your text is saved to local `draft.json` and restored the next time you open the popup.

- Drafts are debounced (400ms) while typing and flushed on hide, close, or quit.
- A successful **optimize** clears the draft for that text — it will not come back on reopen.
- Set `"persist_draft": false` in `config.json` to disable.

Reference React hook (not used at runtime): `ui/reference/usePersistentInput.ts`.

## Run

```powershell
# From the metaprompt folder (with venv active)
python main.py
```

Console-less:

```powershell
pythonw main.py
```

Or double-click `run.bat`.

### Usage

1. Press **Ctrl+Shift+Space** (or your configured hotkey).
2. Type or paste a rough prompt.
3. Press **Enter** — the window expands with the optimized prompt.
4. The result is **copied to the clipboard** as soon as it returns.
5. **Esc** or clicking outside the window hides it (tray process keeps running).

Tray menu: Open MetaPrompt, Open history, Start with Windows, Quit.

Click the **thorough / fast** badge to switch models without editing config.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

## Start with Windows

Tray icon → **Start with Windows** writes:

`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MetaPrompt.bat`

## Project layout

```
metaprompt/
├── main.py           # tray + hotkey + PyQt6 event loop
├── popup.py          # PyQt6 frameless popup + setup dialog
├── api.py            # provider dispatch (Gemini / Groq / OpenRouter / Anthropic)
├── prompt.py         # shared meta-prompt system instruction
├── config.py         # load/save config.json + provider presets
├── secrets.py        # Windows DPAPI encrypt/decrypt for API keys
├── log_config.py     # logging setup + API key redaction
├── history.py        # local JSON history storage + query API
├── history_ui.py     # PyQt6 history browser dialog
├── draft.py          # local draft.json persistence for input bar
├── startup.py
├── config.json
├── requirements.txt
└── ui/               # legacy web UI (reference only; not used at runtime)
```

The API is called only from Python — the popup never exposes your API key.

## Tweaking the meta-prompt

Edit `SYSTEM_PROMPT` in `prompt.py`.

## Troubleshooting

- **Hotkey does nothing** — change `"hotkey"` in `config.json` and restart.
- **Auth errors** — key must match the selected `provider`.
- **Wrong package** — Groq/OpenRouter need `openai`; Anthropic needs `anthropic` (`pip install -r requirements.txt` installs both).
- **Free-tier limits** — Gemini/Groq/OpenRouter free quotas change over time; if you hit rate limits, wait or switch provider.
