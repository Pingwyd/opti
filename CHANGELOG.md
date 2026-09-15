# Changelog

All notable changes to Opti are documented here. Version numbers match `APP_VERSION` in `brand.py`.

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

[1.1.0]: https://github.com/Pingwyd/opti/compare/v1.0.0...v1.1.0
