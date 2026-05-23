# Changelog

## v1.0.0 - 2026-05-24

- Added 9router-first recovery flow for Codex OAuth accounts.
- Added refresh-token hydration for access-only imports by matching email/name against local sources.
- Added import from CLIProxy runtime-auths into 9router.
- Added import from local Codex auth into 9router.
- Added sync from 9router into CLIProxy runtime-auths with backup.
- Added alias/config repair for `gpt-5.5` through 9router.
- Added UI refresh preview showing `fill: 9router`, `fill: cliproxy`, or `fill: codex-auth`.
- Added stale CLIProxy auth quarantine.
