# SDD ledger — plan: docs/superpowers/plans/2026-10-17-rebuild.md

## Status

Task 1: complete (auth and independent entrypoints; real MySQL 8.4 migration and concurrency verified)
Tasks 2—8: pending

## Pre-flight

- Auth identities/sessions -> all API operations: separate role and app factories, shared persistence
- Stable card/version -> favorites/learning/resources/imports: shared stable ID; candidate and published version separate
- Completion -> both frontends/admin statistics: single shared transactional service
- API schemas -> frontend clients: generated OpenAPI; no legacy contract compatibility required after reset
- Shared migration -> independently deployed APIs: expansion-first migration, independent release tags

## Rulings

- Ruling: native worktree tool returned `Not a git repository` for the multi-repository root; use manual sibling Git worktrees for admin/mini/CLI and a new backend repository — preserves original main branches without creating an artificial parent repository — worktrees are not managed attachments in the app
- Ruling: referenced shared parent AGENTS.md does not exist in this supplied workspace; use the approved spec and applicable individual repository conventions — newer user requirement overrides obsolete four-tab behavior — any missing additional historical conventions remain unverified
- Ruling: old business code/tests will be replaced rather than kept compatible; original Git history remains intact — explicitly authorized full rebuild — old binaries cannot be restored against the new empty schema

## Environment

- Backend source: /Users/lubi/Desktop/juya/github-repos/juya-api
- Frontend worktrees: /Users/lubi/Desktop/juya/.worktrees/juya-admin and juya-miniapp
- CLI worktree: /Users/lubi/Desktop/juya/.worktrees/juya-cli
- System lacks Docker/uv/Node on PATH; installing isolated tools and using bundled Node; MySQL verification can run remotely once authenticated
- SSH ED25519 first-use fingerprint recorded: SHA256:1JOgC3coZdjNyB0/jmIr8jAD3E3Bm1vi9/g4efHfkEo
- Default local SSH key is not authorized; account file supplies password and a Windows-only key path; attempting supplied password with verified recorded host key

## Foundation evidence

- Initial authentication suite failed because the new entrypoints did not exist; 10 local behavior tests then passed
- Real MySQL concurrency reproduced duplicate login result insertion, then a duplicate-insert lock upgrade deadlock; atomic no-op upserts fix the actual locking boundary
- Login reservation now precedes one-use code exchange; 4 concurrent identical attempts return one token and redeem code once
- SQLite transaction control explicitly owned by SQLAlchemy to preserve rollback across savepoints; invalid-code retries never return a false successful login
- Ruff and mypy pass; fresh Alembic 0001 creates an empty schema, no administrator or business fixtures
- Reset guard tests reject unrelated/new containers, volumes and application databases

## Legacy cleanup

- Executed authorized inventory-bound cleanup: 8 exact legacy containers, 3 volumes (old MySQL/Redis/imports), four backup directories removed; old runtime profile paths retired
- Provider configuration preserved root-only at /root/juya-rebuild/preserved-config
- OSS list versions and multipart both return 403 AccessDenied (EC 0003-00000001); async request sent for corrected bucket/account permissions, not treated as zero objects
- Ruling: do not substitute unrelated cloud credentials after OSS AccessDenied; continue independent local/DB work — prevents accessing the wrong account — OSS reset and real storage deployment remain pending
