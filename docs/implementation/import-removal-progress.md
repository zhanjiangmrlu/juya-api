# Import deletion and removal — 2026-10-21

Authority: user-approved in-chat plan “修复导入误判重复及上传资料移除”

- Backend base: 3b177a5; frontend base: c45c081 in /Users/lubi/Desktop/juya/.worktrees/juya-admin
- Ruling: reuse the existing clean frontend test worktree and backend test checkout, following the prior import-work ledger's workspace/shared-rule exception; no main-branch changes or deployment
- Pre-flight: backend removal DTOs feed generated frontend contracts; response snapshots must not overwrite unrelated local edits or revive removed records; duplicate rows need separate removal selection
- Baseline from planning: backend import suites 33 passed; original frontend import subset 14 passed; latest test worktree will be checked before frontend changes
- Task 1: complete — deleted modern/legacy identities, old saved status and save fallback now require a live card; explicitly selected deleted targets still fail. Atomic ZIP/item removal retains cards/media/receipts and protects accepted saves. Initial new regressions failed on duplicate/saved status and missing routes, then related45 passed
- Task 2: complete — ZIP and card single/bulk controls, independent removal selection, frozen retryable confirmation, missing-target recovery and refresh. Removed upload/staging caches are pruned; delayed snapshots cannot revive removals or overwrite newer staged edits. Existing row-expansion test retained
- Task 3: complete — final backend211 passed /9 external-only skips, Ruff check/format and mypy49 modules passed; frontend93 passed and full format/lint/style/type checks plus production build passed; both diffs pass whitespace checks
- MySQL: dedicated juya_verify only. Initial targeted run24 passed /1 pre-existing media case failed because ffmpeg was absent from that subprocess PATH. With the correct runtime PATH, that case and two real concurrent removal-versus-parse/save cases passed3/3; additional51-root removal passed1/1. All28 distinct targeted cases now have passing real-MySQL evidence. No shared business SQL/OSS data was used
- Browser: final actual Chrome6/6 passed against a fresh isolated localhost API/worker/SQL/media directory. Covers original multiple-ZIP, multiple-folder and partial-failure flows; deleted-card reimport creates a different ID; duplicate removal survives reload; accepted ZIP removal during another transfer and bulk ZIP removal leave the remaining upload working; single/bulk card removal preserves other folders and source ZIP. Screenshots inspected. Earlier two baseline failures were traced to old private fixtures missing mandatory English titles; corrected fixture data rather than product validation
- Final review: one independent read-only reviewer reported two P2 issues and no declined-to-judge/deferred items. Fixed both in one pass with RED→GREEN regressions: conflicted/unwanted local edits no longer have to save before discard; ZIP-root selection is no longer incorrectly capped by the50-card limit. Removal waits only for previously transmitted/unknown writes, reads current server revisions, and suspends autosave for the selected discard scope
- Concurrent card-list ordering changes were preserved and committed separately by their owning task; this task did not alter them
- Delivery: changes retained uncommitted in the existing test checkout/worktree; no merge, push or deployment. No schema migration. Temporary verification servers stopped after acceptance; evidence and synthetic fixtures remain outside Git

## Authorized remote submission

The user subsequently requested committing and pushing this fix to both remote test branches. Preserve the frontend's concurrent query-button commit by fast-forwarding its existing test worktree before final checks. Commit scope is import source, regression tests, generated contracts and verification records only. SSH transport was unavailable; the existing HTTPS credentials successfully fetched both exact repositories. This submission does not deploy either environment
