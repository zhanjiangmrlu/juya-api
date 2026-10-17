# SDD ledger — plan: docs/superpowers/plans/2026-10-17-rebuild.md

## Status

Task 1: complete (auth and independent entrypoints; real MySQL 8.4 migration and concurrency verified)
Task 2: complete
Task 3: complete
Tasks 5/6 core screens: next (before advanced task4, per the approved vertical delivery order)
Tasks 4—8: pending

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

## Task 2 evidence

- 12 feature assertions initially failed on missing content/media APIs (role isolation already passed)
- Published content is an immutable version; edits stay in the candidate; preview binds revision+hash; stale writes, deleted-card revival and mixed resource references rejected
- Source binding uses explicit UTF-16 ranges for client interoperability; whole-word candidates, manual inflection binding, invalid and overlapping ranges validated
- Real PNG decode/thumbnail, PCM WAV inspection and authenticated byte-range streaming tested locally and with real MySQL
- Native image/audio URLs use opaque 5-minute tickets tied to the actual mini session, current card/version/media; logout and offline revoke subsequent reads
- New migration 0002 verified from an empty MySQL 8.4 schema; Alembic check reports no model drift
- Full real MySQL suite: 32 passed in 86.39s; local: 29 passed, 3 MySQL-only skipped; Ruff/mypy clean
- Ruling: initial media processing is synchronous in Task2; Task4 will move expensive media/import/TTS work behind durable workers before release — avoids shipping a temporary non-durable BackgroundTasks path — interim upload calls are blocking
- User directed rechecking account-related.txt; its explicitly supplied Alibaba AccessKey also returns AccessDenied for both known bucket names. No extra key was requested or printed in logs.

## Task 3 in-progress findings

- Local suite after learning/profiles: 48 passed, 4 real-MySQL-only skipped
- Actual MySQL reproduced two concurrent card completions colliding on the same checkin day despite a user-row lock: the default repeatable-read snapshot was created during authentication
- Fix: explicit READ COMMITTED plus actor serialization; coherent statistics take a shared actor lock. The reproducing concurrency test passed after the change
- Actual commit-failure injection initially received HTTP 200 before persistence; fixed every database yield dependency to function scope so commit finishes before any success response starts
- Durable operation results are now encrypted JSON strings; operation request fingerprints are keyed HMACs so known phone values cannot be guessed offline from a plain body hash
- Source/generated-ID defaults excluded from idempotency fingerprints, so replaying the same raw card request never regenerates identities
- History thumbnails have a separate, ownership-checked resource purpose; neither a last-published original nor audio becomes accessible after deletion
- Task3 tests cover phone/WeChat atomicity, no contact removal, separate versions, no identity merging, encrypted persistence and operation recovery

Task 3: complete — full MySQL8.4 suite 52 passed in 182.92s, including fresh migration0003, concurrent identities, different-card completion race and commit-failure rollback; local 48 passed/4 MySQL-only skips; Ruff/mypy clean

Ruling: implement core admin/mini screens now before advanced imports/TTS tasks — follows the user-approved end-to-end sequence rather than finishing all backends first — generated contracts may expand when advanced features land

Contract integration: response whitelists now generate separate typed APIs; mini list uses page-wide queries for learning/favorite flags and the published admin preview never selects the editing candidate. Three new behavior tests failed then passed; unique OpenAPI operation IDs also tested (HEAD routes remain available but hidden from SDK). Local suite:52 passed/4 MySQL-only skipped; Ruff/mypy clean. Settings repr excludes all credentials and connection URLs.

Admin integration contract follow-up: management rows now identify the published title/thumbnail while retaining the separate candidate. Upload budgets are returned from environment configuration. Both behaviors were RED→GREEN; latest local backend suite54 passed/4 MySQL-only skips; targeted real MySQL contract suite6 passed in22.57s.

Task5 core in progress: rebuilt admin source in isolated worktree with generated schemas, Pinia cookie/CSRF session, explicit retry keys, XHR upload byte progress, full manual editor and source selection, immutable preview/publish, offline/delete confirmation, read-only users/records and A07.10 behavior tests initially passed; browser uncovered publish success navigation blocked by its own busy guard. Added regression RED→GREEN; now11 frontend tests pass. Vue typecheck and production build pass. Actual browser via CUA at localhost verified login→private PNG/WAV upload→save→preview→publish→list and separate saved candidate vs current publication; true empty users/one published card reported by A07. Advanced import/TTS/batch/sort are still pending, so Task5 is not complete.

Ruling: use CUA for all browser actions per its tool instructions; Playwright E2E source is checked in for later user/CI execution but not claimed executed in this session. Browser screenshots under admin docs/verification; local synthetic credentials/media stay outside Git in workspace .private. Local admin API uses a separate SQLite-only verification database, never production or cloud data.

Admin core committed as c5fa1ae in .worktrees/juya-admin. Fresh full checks pass: pnpm check,12 frontend tests, production build (no large initial bundle warning after limiting ElementPlus registration). Added malformed-JSON response regression RED→GREEN: a truncated successful write is reported as unknown and retains the operation key. Browser also verified statistics→published filter and unsaved-leave continue/discard paths. Core phase committed; imports, sorting/batch and pronunciation remain outstanding.

Task6 preflight: mini dependencies installing under Node22/pnpm11.25. Preserved AppID manifest only, then removed obsolete source/tests/build adapters in isolated worktree. New two-tab structure and generated mini contract directories created; implementation not started. Manifest version1.5.0 and production URL checking enabled. Existing main checkout retains all former source/history.
