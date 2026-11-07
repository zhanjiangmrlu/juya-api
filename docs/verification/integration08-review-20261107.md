# 整合08最终复审归档

最终产品提交为小程序afcb378；原I1—I3／D1／D2和追加D3均已批准，无开放Critical／Important／Minor代码发现。下方第一份报告是85a1f5c时的历史阶段结论，其中当时未闭合且描述尚模糊的D3，以第二份afcb378报告和当前[验收记录](integration08-guest-20261107.md)为准。两次复审范围独立，未重复全分支审查或套件测试。API32dfa4e审查通过；后台仅生成契约及文档。

## 原五项范围复审（85a1f5c，阶段归档）

- **I1 — Default unsaved member Progress incorrectly suppresses guest display restoration — ADDRESSED.** `src/sub-packages/listening/use-listening-article.ts:418` now distinguishes a same-version pending draft or persisted `updated_at` from the API default object; `:447` restores the same-version display only when no actual history exists. Actual saved history and valid same-account drafts retain priority. Added regressions cover default API-shaped Progress, saved history, stale/valid drafts and selected pending audio rate.
- **I2 — Late programmatic listening restoration scroll creates a personal PUT — ADDRESSED.** `src/sub-packages/listening/use-listening-article.ts:446` establishes `snapshotReadonly`; the media-state watcher at `:109` and scroll handler at `:852` both respect it beyond nextTick, async measurement and native clamping. Only explicit user actions at `:501`, `:531`, `:542`, `:547`, `:554` lift that boundary. `src/sub-packages/listening/article.vue:123` connects page input, and H5 listeners are removed on hide/unload. New regressions include a genuinely deferred anchor measurement, repeated clamped callbacks, zero progress PUTs without user action and successful saves after user actions. Root also reports the real initial login window had zero personal learning writes; the later PUTs followed user-confirmed scrolling and are not evidence of this defect recurring.
- **I3 — Valid listening category return resets captured scroll to zero — ADDRESSED.** `src/sub-packages/listening/use-listening-catalog.ts:140` now rebuilds/validates the list before replay; `:145` restores its loaded range then position, and generation/list-instance guards reject late identity changes. `src/shared/types/navigation.ts:8` keeps loadedCount in the in-memory snapshot. Added success/cancel tests cover retained category, offset and loaded pages; a separate all-category invalidation test rejects stale replay. Existing removed-category fallback remains intact.
- **D1 — iPhone list/detail thumbnails fail while original opens — ADDRESSED for the observed iPhone/LAN preview path.** `src/services/local-image.ts:6` downloads authorized HTTP images without relying on the DEV flag; detail now uses it at `src/sub-packages/scenes/detail.vue:792`, matching the list path. HTTPS/H5 behavior stays distinct. The added production-build VM test executes the actual compiled helper and verifies HTTP→temporary file and HTTPS→original URL. Safe native diagnostics independently show successful local list/detail image loads in the latest preview, and root relayed the user's confirmation that thumbnails and original images work. No unsupported-WebP assumption or media-format conversion was introduced.
- **D2 — iPhone 1.5× fails, with an accompanying summary burst — ADDRESSED for the original speed defect and the reproduced duplicate-play feedback path.** `src/services/background-audio-port.ts:201` stages a rate while preserving position and rebinds before explicit playback; `src/services/audio-controller.ts:127` keeps a pending value and `:191` confirms it only after native onPlay and actual readback. `background-audio-port.ts:97` ignores duplicate play notifications while already running; genuine external resumes still pause and invoke the existing permission gate. Native rejection remains visible. Added tests exercise delayed stop/pause/play, last-selection wins, paused selection without playback, cancellation by pause/PDF/word/dispose and genuine native termination. Safe logs corroborate real 1.5× media-clock progression and successful 1.75× samples, beyond property readback. The original approximately 15/s burst's exact cause remains unproven; it is not represented as conclusively diagnosed.

## New Breakage in the Fix Diff

- **Critical: None verified. Important: None verified. Minor: None verified.** Reviewed only the supplied mini fix package `1dd3ff7..85a1f5c`, including the audio staging/rebinding state, pending-rate cancellation, late native callbacks, listening display/persistence boundary, HTTP image path and gated diagnostics. No API/admin re-review or source edits.
- **Diagnostic isolation check:** `src/services/native-diagnostics.ts:99` limits reports to enabled builds, a configured endpoint, bounded counts and whitelisted fields; original paths, URLs, content identifiers and raw errors are not forwarded. `vite.config.ts:14` makes the build flag statically eliminable. Inspection of the produced production JS found zero `native-play`, `image-info`, `rate-stage` or diagnostics-endpoint-variable markers; the remaining diagnostics module is a 45-byte stub.

## Out-of-Scope Observations / Native Validation Limits

- **Listening consecutive-rate-change stop remains open.** The user clarified the earlier ambiguous report: on the listening page, playback changed from 1× to 1.5×, then from 1.5× to 1.75×, and “此时就暂停了”. This supersedes the initial interpretation that pressing pause failed to stop playback. The exact native callback sequence and causal connection to the fix diff have not yet been established. The inspected diff has tests for pending-rebind cancellation, and this review found no demonstrated causal connection between the report and a changed line. This is an unresolved device acceptance observation, not a proven new fix-diff defect and not a reason to claim complete audio acceptance. Root/original implementer is investigating it separately; retain it in the handoff until reproduced and closed.
- **Remaining native scope:** Android, broader system/headset controls and background recovery remain unverified by this review. The current iPhone PDF open/return-paused/position/rate workflow was reported successful by the user; it should no longer be mislabeled as untested. Root also relayed successful real WeChat login, no automatic favorite and successful subsequent explicit favorite. Those user/controller observations do not certify every login/media scenario or all T01–T379 cases.
- **Other entirely out-of-diff code observations:** None.

## Checks Reviewed

- **Fix package and original findings:** Read `final-fix-brief.md`, `final-fix-report.md`, original `final-review.md` and the supplied net fix diff in focused passes. All source paths above resolve under `/Users/lubi/.codex/worktrees/juya-miniapp-integration08/juya-miniapp`. Did not derive a new diff or run git mutations.
- **Recorded test/check outputs inspected:** `/tmp/juya-final-full-test-3.log` ends with 121 files / 699 passed; `/tmp/juya-final-check-3.log` confirms formatting, ESLint, Stylelint and vue-tsc; H5 and local MP logs show successful builds, 18 pages, three tabs and shared audio main-entry verification. Read the changed tests and their assertions rather than treating the totals alone as proof. No suites or focused tests were rerun because the code/tests/native evidence resolved the scoped questions without an unanswered reproducible code doubt.
- **Budget/build evidence:** The report names unchanged strict 450×1024-byte contracts and production main package 459503B. Their recorded full-suite run is passing; the actual production helper regression is present in `tests/contracts/wechat-release-build.spec.ts`. No limit increase, removed assertion or upload/deploy command was introduced by this diff.
- **Safe device evidence inspected:** Parsed only whitelisted fields from `device-fixture/native-diagnostics.jsonl`; the latest observed segment (14:50:45–14:56:40 UTC) contains 8 successful local image loads and no `resume-start` event. Real media-clock samples include approximately 1.9s per 1250ms at 1.5×. A read-only aggregate of the redacted request log in that same window found at most 3 summary requests in one second, not the earlier burst. This is a bounded observation, not a root-cause claim or blanket native-audio pass.
- **Read-only boundary:** No source/test/checkout/index changes, no subagents, no credentials or private.json reads. This report is the sole authored review artifact.

## Verdict

**Fix round: All I1–I3 and the original D1/D2 findings addressed; no new verified Critical/Important breakage. Scoped code review approved at `85a1f5cfe20427653e917e5c9832e1b3518e68a8`.**

**Overall native acceptance remains open:** the newly reported listening consecutive-rate-change stop and the remaining device/platform scenarios are not closed by this scoped approval.


## 听读暂停追加范围复审（afcb378，最终）

# D3 scoped re-review

Verdict: **APPROVED** for miniapp `85a1f5c..afcb378b00223e072f4cb0675539e7947d8e085f`.

Reviewed the supplied `review-85a1f5c..afcb378.diff`, `device-pause-brief.md`, and `device-pause-report.md`; followed only the changed native-play guard, its cancellation callers, and added diagnostics/tests. No source edits, new subagents, broad review, test-suite rerun, credential/private configuration access, or API/admin re-review. File references below are relative to `/Users/lubi/.codex/worktrees/juya-miniapp-integration08/juya-miniapp`.

## Original issue

**D3 — ADDRESSED.** The precise defect is the listening player’s UI/native playback disagreement after rate changes, observed as tapping pause changing the button while audio continued. The trace-supported cause is an owned native onPlay discarded because its actual paused-property guard transiently remained true; it is not a claim that 1.75× is unsupported or that native pause universally fails.

`src/services/background-audio-port.ts:109–129` now rejects a paused-property play event only when no controlled start is pending. A pending owned start is acknowledged, its starting flag is consumed, and the controller receives the native callback. `src/services/audio-controller.ts:262–292` still verifies playback intent and confirms the staged rate through the existing real native readback; this patch does not synthesize successful rate values or auto-start on a timer.

Cancellation protections remain effective for this changed condition:

- Explicit pause clears the port starting flag and running state before calling native pause (`background-audio-port.ts:367–375`). A subsequent stale play with paused=true therefore still returns at the guard; an event while the explicit pause command is pending and paused=false is paused again (`:148–156`). The controller independently rejects play when fullIntent has been cancelled (`audio-controller.ts:266–268`).
- Word playback cancels fullIntent and pending rate rebinding and pauses an in-flight full start (`audio-controller.ts:442–455`). PDF suspension calls pauseFull and cancels the word path (`:593–615`). Neither can qualify for the newly allowed starting branch after cancellation.
- Leaving/disposal clears controller intent and destroys the port; the port loses ownership/alive status and callbacks (`audio-controller.ts:619–633`, `background-audio-port.ts:390–401`). The active-owner guard precedes the modified check (`:100–109`).
- External/system play still enters the existing hold-and-authorize flow; the patch adds no resume call to the controlled-start branch. Its revision checks and authorization callback remain at `background-audio-port.ts:210–219`.

The new regression at `tests/unit/services/background-audio-rate.spec.ts:192–231` models the first paused-property read returning stale true, verifies confirmed 1.5× then 1.75×, and then checks explicit pause plus a late play event. Existing actual-port/controller cancellation cases at `:126–144` cover pause, PDF, word and disposal while a rebind is pending, including late stop/pause/play and no resume call. These tests exercise the relevant boundary rather than only checking source strings.

## Evidence checked

I read the final existing command outputs: `/tmp/juya-device-pause-final-test.log` reports 121 files / 702 tests passed; `/tmp/juya-device-pause-final-check.log` ends with successful formatting, lint, stylelint and type-check commands; the H5 and MP logs report completed builds, and MP verifies 18 pages, three tabs and shared audio loaded by the main entry. No tests were rerun. The implementer/root production result is 459579 bytes below the unchanged 450 KiB budget, with default production diagnostic markers absent; this is reported build evidence, not a newly executed build in this review.

I independently read only the allowed safe native diagnostic batches after `pause-fixed-start.json` (`previous_batches=185`, 15 new batches):

- seq77 acknowledges the controlled start with actual guardPaused=true; seq84 shows the same port1/controller1 playing at 1.75, with pendingRate=null, fullStarting=false and rateRebinding=false.
- seq88 begins the explicit pause; seq96 forwards native pause. seq97 is the next user toggle 9012 ms later, still paused with fullIntent=false at position 11.02. The next port-play is seq103, after that manual toggle.
- seq107 acknowledges manual resume; seq113 is playing at 1.75 from position 11.02. seq118/119 advance approximately 2.19 media seconds per 1.25 wall seconds, consistent with 1.75×.

Together with the user’s explicit confirmation that pause, remaining paused and manual resume are normal, this closes the specific reported iPhone D3 sequence. The safe trace covers a nine-second pause interval; it is not an unlimited-duration or all-device assertion.

## New breakage

**None found in the scoped diff.** Critical: none. Important: none. Minor: none.

The added port/controller diagnostics are gated by the existing explicit QA flag. State-change sampling excludes position-only updates while preserving the ordinary changed-state callback (`audio-controller.ts:117–144`). The action decorators preserve argument/return/exception behavior and only decorate QA subscriptions/actions (`:250–260`, `:649–656`). Diagnostic instance IDs are process-local WeakMap counters, and new output fields are finite numbers/booleans or fixed enum labels (`native-diagnostics.ts:20–31`, `:54–115`, `:169–197`); they introduce no account/content identifier, arbitrary URL/error-text export, business write, retry loop or playback action. Existing queue/event bounds remain.

## Out of scope / declined to judge

No additional out-of-scope finding was discovered. Original I1–I3 and D1/D2 approvals remain closed. API/admin behavior and untouched guest/login flows were not reopened. Android, headsets/system controls across devices and formal live-platform release validation are not established by this scoped iPhone review. No claim of deployment or official WeChat version upload is made.

## Final assessment

D3 is **ADDRESSED** and this scoped change is **APPROVED**. The modified guard matches the measured native event ordering while preserving cancellation, authorization and real rate confirmation boundaries. There is no verified new regression requiring another fix wave.
