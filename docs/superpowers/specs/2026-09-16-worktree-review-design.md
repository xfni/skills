# Worktree Review Design

Approved scope: reviewers autonomously explore the current worktree; the root supplies background rather than a selected evidence subset. Reviewers return results through stdout/API and never write the worktree. Controller-owned output is written only after post-review verification.

The controller captures HEAD, raw index identity, and file content/mode/link identities before review. Only exact controller bookkeeping paths and caches/dependencies are excluded from comparison; `.ai` inputs are not globally excluded. A private filtered frozen view contains all eligible project source, tests, configuration and artifacts, not just caller-selected files. Credentials, raw production data, symlinks, caches, dependencies and binary/oversized inputs are omitted and listed as gaps. The target and its registered upstream chain must be present. Both original worktree and frozen view must remain unchanged before any report is accepted. Mutation invalidates the attempt; no automatic rollback.

Cursor uses its SDK with plan mode and read/grep/glob/ls tools against the private view. iBrain uses Responses with bounded list/read/search functions implemented locally against the same declared view. No shell, writes, arbitrary URL or worktree-external reads are exposed. All exploration returns through API; controller stores the terminal report and exploration evidence.

Explicit Flow/review invocation supplies Cursor's stage/run review scope without a separate human external-review gate. iBrain is organization-approved and needs no authorization record. Production-derived data replay retains its existing human decision and safety contract. Existing external_review decisions are historical records, not runtime gates; single-use package bindings remain mechanical input/snapshot identities.

Legacy iBrain malformed-frame attempts can be marked ineligible through the audited repair command without altering original evidence or manufacturing PASS. Real timeout attempts remain eligible. Conflicting reports remain non-degradable. Existing GPT/Cursor/iBrain/consistency review topology remains unchanged.
