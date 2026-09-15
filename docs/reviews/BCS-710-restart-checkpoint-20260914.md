# BCS-710 restart checkpoint

Recorded before host shutdown on 2026-09-14.

## Workspace

- Worktree: `/Users/nixiaofeng/工作/code/feature-BCS-710-flow-coder`
- Branch: `feature-BCS-710-flow-coder`
- Codex session: `01a08f10-1279-7872-bb7d-102a87056dc8`
- Changes are intentionally uncommitted. Preserve all tracked modifications and untracked Flow v2 files.

## Current objective

Finish the executable Flow v2 controller and its skill integration. Mechanical workflow facts must be enforced by `flowctl`, including artifact digests and approvals, arbitrary-node and multi-milestone resume, route-back invalidation and revision high-water marks, review ordering/binding, Cursor runtime classification, pause signals, snapshots, transactional state, and handoffs.

## Verified state

- Latest local verification: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v`
- Result after resume: 64 tests passed in both the source worktree and the deployed global copy.
- `git diff --check` passed.
- The most recent GPT-6 Astra/medium review passed before the subsequent Cursor findings were fixed.

## Latest Cursor findings and fixes

Cursor found that a paused run could be cleared by route-back and that missing/truncated terminal output could be degraded through keyword matching. Both were fixed:

- while `FLOW_RUN_HUMAN_GATE` or `FLOW_RUN_BLOCKED` is pending, only a bound `FLOW_RUN_RESUMED` signal is accepted;
- resume/handoff and state-changing operations preserve or enforce the pause;
- `finished without terminal report` and terminal JSON fragments are `UNCLASSIFIED`, not degradable `RUN_ERROR`;
- tests cover paused route-back, explicit resume, missing terminal output, and truncated FAILED JSON.

## External review completion

A Cursor re-review was running when shutdown was requested:

- Cursor agent: `agent-5d55bfd1-4de6-4e0c-8d32-4d9cd3d1e543`
- Cursor run: `run-0e12e55b-da93-4eb2-a9a2-ad491039044a`
- Prompt: `docs/reviews/bcs-710-flowctl-cursor-review.md`

That process was interrupted. After resume, the review loop continued through additional reproduced fixes. The final Cursor review returned `PASSED` with no blocking findings. The Flow v2 controller, contracts, schemas, and nine skills were then synchronized to `~/.codex`, byte-compared with the source, validated, and tested from the global copy.

## Remaining disclosed architecture note

The caller-supplied `--runner` path remains an open non-blocking trust-root issue: the controller proves it executed the configured runner, not that the runner is independently trusted. Cursor also noted that manually using `review begin --backend cursor` can leave an orphan STARTED attempt; normal Flow uses `review cursor` and is unaffected. Do not silently mark either item resolved.

## Resume command

```sh
codex resume 01a08f10-1279-7872-bb7d-102a87056dc8 --add-dir '/Users/nixiaofeng/工作/code/feature-BCS-710-flow-coder'
```
