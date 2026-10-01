# Lanes

One lane per unit of work. Claim before you build; someone else accepts.
Run `./lanes.py board` to see it sorted, `./lanes.py check` before you commit it.

## L-001 Retry wrapper around the upload client
- state: done
- owner: claude-a
- scope: src/upload.ts, src/upload/**
- evidence: PR #412 @ 9c0d11e
- accepted_by: nick
- note: declined by nick: drop 409 from RETRYABLE in upload.ts:88

## L-002 Empty state for the search page
- state: awaiting_acceptance
- owner: codex-b
- scope: web/search/**
- evidence: PR #418 @ 51be07a

## L-003 Rate-limit the export endpoint
- state: claimed
- owner: claude-a
- scope: src/api/export.ts
- story: Exports stop timing out for everyone when one team exports a year of data

## L-004 Upgrade the test runner
- state: open
- scope: package.json, vitest.config.ts
