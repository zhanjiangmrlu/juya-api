# Multi ZIP import implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this approved plan task by task

**Goal:** Select and append multiple ZIPs, review every folder in one batch, and save selected cards as drafts with isolated failures and safe retries

**Architecture:** Reuse per-file uploads, existing batches and per-card save jobs. Add archive provenance, persisted parsing counters and stable incomplete-object identity. Keep the three-step workflow and explicit publication

**Tech Stack:** Vue 3, TypeScript, FastAPI, SQLAlchemy, Alembic, Celery, pytest, Vitest and Playwright

**Spec:** User requirements and approved seven-part design in the current conversation; baseline ../../../句芽英语-原型与设计稿/需求基线-20261017.md sections 17–18 and 27.8

## Global constraints

- One card per folder; DOCX mode retains multi-card documents
- Match by archive ID plus full folder path, never names alone
- Draft-only import; incomplete media permits drafts after invalid references are removed
- Preserve revisions, ownership, CSRF, idempotent receipts and job lease fencing
- Preserve deployment upload/card limits; do not deploy or alter shared business data
- Follow frontend kebab-case, script setup, SCSS and documented arrow functions

## Review focus

- Renamed identical incomplete archives must not create duplicate drafts
- Same paths in different archives must not mix images or audio, even on staging requests
- New uploads or media completion must invalidate stale save confirmation
- Queued cancellation and upload response loss must never silently replay a successful file
- A failed-save retry must exclude newly added and previously successful cards

### Task 1: Backend provenance, progress and identity

**Files:** import_models.py, import_service.py, import_api.py, worker.py, schema.py, application.py, migrations/versions/0011_import_progress.py, tests/test_multi_zip_imports.py

**Interfaces:** Extend ImportFileView with nullable progress; extend ImportItemView with source_zip_id, source_zip_name and source_folder. Add optional item_ids save/confirmation scope for failed-only retries. Preserve old request shapes

- [x] Add tests for three ZIPs, three folders, matching isolation, incomplete duplicates and scoped retries; watch missing behavior fail
- [x] Implement derived provenance, lease-guarded progress, stable identities, source validation and scoped confirmation
- [x] Verify import suite, migration and static checks

### Task 2: Upload queue

**Files:** import-upload-panel.vue, use-import-uploads.ts, import types, upload tests

**Interfaces:** Queue before starting; one active upload; additional pending files append; refresh/uploading/pending events preserve page guards

- [x] Test selection without uploading, removal, appending, serial execution, failure continuation and stable retry keys
- [x] Implement the queue and progress presentation using existing HTTP upload client
- [x] Run upload tests and typecheck

### Task 3: Unified review and scoped save retry

**Files:** import-workflow-page.vue, import-review-list.vue, import-asset-picker.vue, import-save-step.vue, import staging and generated contracts

**Interfaces:** Display archive provenance and scoped candidates; summary separates archive/card failures; failed-only retry freezes failed IDs and fresh confirmation

- [x] Test provenance/candidate isolation, pending queue guards, stale confirmation and failed-only retry
- [x] Implement UI, preserve per-card edits and regenerate API types
- [x] Run frontend tests, check and build

### Task 4: End-to-end verification and review

**Files:** tests/e2e/multi-zip-import.spec.ts, verification notes

- [x] Exercise real API, isolated SQL and worker plus browser multi-ZIP selection/review/draft save
- [x] Verify partial failure, incomplete draft publication refusal, duplicate reimport and retained single-ZIP/DOCX flow
- [x] Run both full suites and static/build gates; run fresh whole-change code review and fix important findings
- [x] Record actual results and remaining environment limitations
