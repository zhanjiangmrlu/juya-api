# SDD ledger — plan: docs/superpowers/plans/2026-10-17-rebuild.md

## Status

Task 1: in progress
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
