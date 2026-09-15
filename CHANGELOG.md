# Changelog

All notable changes to Opti are documented here. Version numbers match `APP_VERSION` in `brand.py`.

## [1.2.0] - 2026-09-15

### Added

- **Settings → Data:** export/import backup (settings, projects, API keys) for migrating between dev, portable, and installed data folders.
- **Projects pane:** project type, tech stack, and conventions fields aligned with prompt injection; **Save / Cancel** with unsaved-change prompts; **+ New project** pinned above the list.
- **`projects.json`:** project profiles stored separately from `config.json` (only `active_project` stays in config). Legacy `config.json` `projects` migrate on first load.

### Changed

- Project edits no longer auto-save on every keystroke — use **Save** to persist.
- Backup format v2 includes a top-level `projects` object; v1 backups (projects inside `config`) still import.

## [1.1.0] - 2026-09-15

### Added

- Redesigned history browser (search, detail pane, row actions, persisted window geometry).
- Encrypted per-provider API keys (`vault.json` / DPAPI) and related settings UI.
- Transform modes UI, target window selector, and window service for inject targeting.
- Rate-limit dialog and expanded test coverage.

### Fixed

- System tray and global hotkeys: all Qt UI work is marshaled to the main thread (tray menu and hotkeys respond reliably).
- Startup order: popup window is created before the tray thread starts.
- Quit/shutdown path uses queued signals on the main thread.
- Inject, API retry, and PyInstaller/CI installer build fixes from prior work on this branch.

[1.2.0]: https://github.com/Pingwyd/opti/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Pingwyd/opti/compare/v1.0.0...v1.1.0
