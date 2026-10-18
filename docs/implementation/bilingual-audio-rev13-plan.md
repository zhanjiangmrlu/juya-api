# CHG-0015 implementation plan

Spec: `/Users/lubi/Desktop/juya/句芽英语-中英文标题与多ZIP多音频格式需求-独立增补版-20261018.md`

Approved approach: evolve the unified API, existing administration frontend and uni-app frontend; preserve stable card IDs and immutable publication versions. Scope N01–N29, revision 13's 21 specified frames.

## Task 1: bilingual content and DOCX

Extend the existing Chinese `name` with independent `title_en`; use these canonical fields in all published and candidate responses, summaries and search. Old payloads read with empty English without rewriting version hashes. Require both titles for new publication, allow incomplete drafts and independently optional vocabulary meaning/phonetic. Parse scoped English metadata and retain readable content on conflicts; update example. Test real HTTP draft/publication/search/summaries and DOCX boundaries/conflicts before implementation.

## Task 2: audio normalization

Preserve immutable Media originals. Link deterministic MP3 playback derivatives, store actual formats/durations, fully decode and compare conversion output before readiness. Authorized delivery resolves playback only after checking the logical original's card/version authorization. Existing four-format upload and multi-ZIP isolation/recovery are reused. Verify actual codecs and transient retries, original retention, Range and publication gates.

## Task 3: administration

Regenerate contracts. Extend editor, reader, list, import review/target selection with two independent titles, optional meaning and audio processing/ready/error states. Update help and downloadable example. Test save/reopen, search and incomplete import workflow; preserve queue/cancellation/recovery.

## Task 4: mini-program and revision 13

Regenerate contracts, display published dual titles across lists/details/favorites/records. Extend the current full-audio controller and session state to five rates; retain pause/position, independent normal-speed word audio, lifecycle and error behavior. Verify 1.75 capability without claiming device acceptance. Read specified Figma contexts and apply vocabulary/chunk sizes and conditional fields, U07 compact groups and U06 centered statistics.

## Task 5: integration, review and evidence

Run backend suite, checks and real MySQL/Redis verification when available; both frontend suites/checks/builds, browser visual checks, final independent code review. Record N01–N29 evidence with real device items explicitly pending until tested. No production deployment or destructive business-data changes in this development scope.

## Shared interfaces and verification

- Tasks 1/3/4 share generated role-specific OpenAPI contracts and immutable publication semantics.
- Tasks 2/3/4 share logical source media identity; playback derivation must not alter import/card identity or leak private resources.
- Tasks 1/2 share publication readiness; failed upload/conversion must preserve previous effective references.
- Test commands: API `.venv/bin/python -m pytest -q`, Ruff/mypy; frontends `pnpm test`, `pnpm check`, admin `pnpm build`, mini `pnpm build:mp-weixin` and H5 visual build.

## Execution ledger

- Started from API ad3f717, admin 9f7b59e, mini f79e8bd; all clean. Existing frontend linked worktrees reused, feature branches `codex/bilingual-audio-rev13` created. API work stays on a dedicated feature branch in the existing checkout to preserve the established local runtime paths.
- Shared parent AGENTS.md remains unavailable as established in the earlier task; apply readable repository rules and the user-approved CHG-0015 baseline.
- Real iOS/Android playback and native visual acceptance require actual devices; automated results will not be represented as device evidence.


## Execution result — 2026-10-18

Tasks1–4 implemented. Task5 code review and automated/browser integration complete; real iOS/Android acceptance remains pending. Detailed N01–N29 evidence is in `docs/verification/rev13/acceptance.md`.

- TDD regressions cover title metadata scoping/conflicts/legacy hashes and whole-version summaries; actual four-format codecs across single upload/ZIP/DOCX, original retention, Range and retry; controller rate behavior and revised components.
- Independent whole-change reviewer found3 issues: VBR AAC duration estimate, legacy non-MP3 publication bypass, and single-DOCX conflict visibility. All3 reproduced RED, fixed, then verified GREEN. Single-DOCX now explicitly confirms titles and text while retaining media; this is the approved new title import behavior, replacing the old text-only confirmation.
- Full final scoped backend174 passed/7 external-only skips; Ruff/format/mypy48 modules pass. Real MySQL full177 passed/1 Redis-only skip before review; final title/audio suite24 passed on real MySQL after fixes. Actual Redis/Celery1 passed. Admin63 and mini50 tests plus checks/builds pass.
- Figma revision13's21 specified contexts fetched with screenshots; measurements from real H5 DOM20/20/16/16px, rows48px, logout27.984px, records column center deltas0. Browser actual rate ratios1.048/1.204/1.501/1.749/1.993. H5 audio wrapper lacked rate forwarding, so the shared port now uses real HTMLAudioElement for H5 and existing native context for WeChat.
- Ruling: official WeChat typings specify continuous playbackRate0.5–2.0, including1.75, despite uni documentation's abbreviated list. Native implementation uses property readback and visible failure; actual phone proof is still required.
- Ruling: additive0013 stores playback linkage and frozen receipt English titles; old publication JSON/hashes are not rewritten. Ready legacy originals remain readable while explicitly preparing playback, and new publication requires readyMP3.
- Concurrent local-share work appeared in allthree checkouts. Those source/tests/configuration are outside this task; preserved, excluded from this task's staging, and scoped Python checks exclude its two newly added Python files. Do not attribute those changes or previous failures to CHG-0015.
- No production or test deployment, no remote push/merge. Reused worktrees and dedicated branch remain available for later device testing and release.
