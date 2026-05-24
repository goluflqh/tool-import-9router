# Changelog

## v1.0.6 - 2026-05-24

- Replaced the plain `README.txt` with a polished GitHub-rendered `README.md`.
- Reorganized documentation around local quick start, VPS alias workflow, account transfer, UI actions, and safety model.
- Documented the preferred `9router-vps` alias flow and the VPS database path `/home/deploy/.9router/db/data.sqlite`.

## v1.0.5 - 2026-05-24

- Added a redacted 9router API key guard around SQLite write actions.
- Import, repair, and duplicate cleanup now warn if the `apiKeys` table is empty or changes while the tool writes provider accounts.
- The guard only stores key hashes/metadata in responses and never exposes full API keys.

## v1.0.4 - 2026-05-24

- Added checkbox selection for existing 9router accounts.
- Added `Export đã chọn` to export token JSON for only selected accounts.
- Added checkbox selection in JSON file import so users can import only selected accounts.
- Updated VPS docs to prefer `IMPORT9ROUTER_DB_PATH` on Linux shells.

## v1.0.3 - 2026-05-24

- Added instance naming for local/VPS separation.
- Added custom SQLite path via `9ROUTER_SQLITE_PATH` or `IMPORT9ROUTER_DB_PATH`.
- Added `IMPORT9ROUTER_NO_BROWSER=1` for headless VPS use.
- Allowed localhost SSH tunnel ports that differ from the server's internal port.

## v1.0.2 - 2026-05-24

- Added `Lọc trùng email` action for 9router accounts.
- Added safe SQLite backup before removing duplicate email rows.
- Added refresh hydration preview for JSON file import.

## v1.0.1 - 2026-05-24

- Clarified that free accounts can be added when their token is valid, but model access remains limited by the account plan.
- Renamed UI actions with clearer Vietnamese labels and accents.
- Simplified import/sync button wording while preserving the 9router-first workflow.

## v1.0.0 - 2026-05-24

- Added 9router-first recovery flow for Codex OAuth accounts.
- Added refresh-token hydration for access-only imports by matching email/name against local sources.
- Added import from CLIProxy runtime-auths into 9router.
- Added import from local Codex auth into 9router.
- Added sync from 9router into CLIProxy runtime-auths with backup.
- Added alias/config repair for `gpt-5.5` through 9router.
- Added UI refresh preview showing `fill: 9router`, `fill: cliproxy`, or `fill: codex-auth`.
- Added stale CLIProxy auth quarantine.
