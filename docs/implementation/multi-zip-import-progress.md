# Multi ZIP import execution ledger

Plan: ../superpowers/plans/2026-10-17-multi-zip-import.md

User approved design on 2026-10-17. Backend base 7821097; frontend base 92152b3

Ruling: reuse the existing frontend linked worktree and backend test checkout — preserves the approved rebuilt sources and avoids creating another checkout attached to an unrelated workspace root; no main branch edits. Subsequent authorized test deployment is recorded below

Ruling: the referenced parent AGENTS.md is absent from all current workspace roots — proceed under the approved requirements and readable repository rules, as the user approved after this limitation was disclosed; unknown additional rules cannot be claimed satisfied

Pre-flight: backend DTO additions feed generated frontend contracts; keep additions optional for stored operation receipts and update every typed test fixture. Save retry scope must be shared by confirmation and execution; appending ZIPs must invalidate the reviewed digest

Task 1: complete — full local backend suite 133 passed / 7 external-only skips; Ruff/format/mypy passed. Thirteen new import regressions include three archives, nested three folders, server-enforced media isolation, incomplete duplicates, same-batch duplicate reporting, scoped retries, stale confirmation including async media completion, progress fencing, legacy identity after unsaved media edits and preserved DOCX kind conflicts. Two additional worker health cases verify role-specific schema floors

Task 2: complete — seven actual upload component tests plus asset isolation regression, including pending removal, append during transmission, failure continuation, original DOCX entry, unknown-response key reuse, cancellation and the cancel-during-receipt race

Task 3: complete — frontend full suite 42 passed; format/lint/style/type checks and production build passed. Failed-only confirmation scopes both request and visible save list

Ruling: progress uses additive migration 0011 after the existing timestamp migration 0010; the new admin requires 0011 while mini retains 0010 — avoid claiming readiness on a database missing the new column without forcing a mini deployment

Task 4: complete — actual MySQL latest15/15 passed: all13 import regressions, fresh migration to0011 plus Alembic model check, and concurrent worker lease claim. Initial wider run36 passed/1 fixture setup failure caused by retained Alembic table; corrected the fixture to clear only this dedicated verification database's version table. Real Redis/Celery delayed-dispatch and duplicate-delivery test1/1 passed. Actual Chrome import suite3/3 passed on final production code, with screenshots checked; original publication smoke1/1 passed again after final patches. Final frontend check passed and both repository diffs have no whitespace errors

Final review: fresh independent reviewer found two Important issues; both reproduced with failing tests and fixed in one pass

Final: fixed cancellation during a receipt query — confirmed receipt now wins over transport cancellation; queue test RED→GREEN, frontend42/42 passed

Final: fixed legacy incomplete identity after unsaved staged media changes — recover by saved canonical content hash rather than only mutable staged media; regression RED→GREEN, backend133 passed / 7 external-only skips and real MySQL15/15 passed

Final: fixed DOCX-mode file-kind conflict regression independently identified before the review result — preserve prior filename/hash conflict lookup, avoiding a uniqueness error; regression RED→GREEN and real MySQL passed

Final: schema floor checked consistently by admin API, admin Worker probe, release preflight and bootstrap; mini remains compatible with0010. New admin Worker probe regression RED→GREEN

No review findings deferred. Implementation verification did not modify shared business data. The user subsequently authorized committing and deploying to test

## Authorized test release — 2026-10-17

- Feature commits pushed to `origin/test`: backend `e503442bd5439615b615303eebc25f5ab082ede9`, frontend `5e7e261e9a6e0e9b6521775ff78363ae8d1a13e8`.
- [GitHub Actions run 39041233684](https://github.com/zhanjiangmrlu/juya-api/actions/runs/39041233684) passed quality checks with actual MySQL/Redis and both role image jobs. Only the admin image was deployed. Admin artifact 12104056954 ZIP SHA-256 `adc8fa8ee4b3e7799430ddb7b78bd560d0dfc6623f1199c5837e72655b8cfb06` was verified before packaging; native CLI also checked the inner archive and OCI identity.
- Used the existing Juya CLI release engine; only SSH transport was adapted for the existing password login, with strict known-host verification. Repeated local release gates passed: backend 133 tests / 7 external-only skips plus Ruff/format/mypy; frontend 42 tests, full checks and test-configured build.
- Explicit compatible migration completed first; actual test database reports `0011`. Management API, Worker and dispatcher then deployed as `20261017T143926-e503442bd543-98d7dc`; previous release remains `20261017T130435-6aca4f47e516-a093cd`. Native public-health finalization and test retention completed without warnings.
- Admin web deployed as `20261017T144627-5e7e261e9a6e-f75743`; previous web release remains `20261017T125435-92152b326627-0007d7`. Test web assets and configured API base passed the native release validation.
- Actual new Worker image passed seven isolated temporary-SQLite/media regressions: three ZIP sources, three folders in one ZIP with persistent progress, source media isolation, incomplete duplicate recovery, renamed identical ZIP reuse, stale confirmation rejection and duplicate reporting during save. These probes did not write shared SQL/OSS business data.
- Actual Chrome login at [test admin](https://test-admin.juyayingyu.com/imports) succeeded; multi-ZIP and original DOCX entries and draft-only notice are visible. No browser runtime errors or HTTP 5xx occurred; screenshot inspected.
- Both public test API readiness endpoints return HTTP200/ready. All three admin containers are healthy on `e503442`, with zero restarts/OOM. All three mini containers retain their exact prior IDs, images, start times and health. Production resources were not deployed or restarted; no business-data cleanup or database downgrade was performed.

Existing capacity and browser pending-file persistence limitations remain as documented in the frontend verification report. Full cloud import was not repeated against shared business data; the cloud image regressions above used private temporary storage, supplementing the earlier real-MySQL/Redis and complete browser flow verification.
