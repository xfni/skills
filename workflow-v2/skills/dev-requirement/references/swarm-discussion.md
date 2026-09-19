# Swarm discussion protocol

This is the Requirement moderator's discussion method, not an additional controller schema or approval gate. Borrow grilling's question tree, dependency frontier and recursive boundary challenge here; no installed grilling dependency is required. Grouped questions are for the two explorers, not a replacement for human brainstorming's one-question-at-a-time conversation or Intent's stage boundary.

## Roles and shared record

Keep a lightweight question map and important conclusion record, scaled to the need. An entry has a stable reference, conclusion/question, source locator, applicable conditions, fact/inference/unknown label, and relevant objection or replacement relation. No exhaustive forms for trivial items. Preserve earlier human discussion and distinguish confirmed choices from Agent suggestions; explore omissions rather than repeat settled interviews.

Both explorers can build and criticize. For each theme name a lead and a cross-challenger: value leads outcomes/scenarios/alternatives/smallest delivery; risk leads failed assumptions/abnormal cases/constraint interactions/stakeholder harm. Cross-checking does not require repeating the whole analysis. The moderator additionally asks what neither role considered and checks the original user purpose, failure consequences and hidden common assumptions.

Round 1 receives the same source baseline but neither peer output nor the moderator's preferred option. Independence means independent judgment, not forgetting prior human context. Later rounds share both roles' original structured substantive outputs and evidence references, plus the moderator's synthesis and amendments. Summaries must not drop conditions or promote inference to HUMAN evidence. Share conclusions, not private reasoning, secrets or unauthorized material.

For a new exploration, start both role threads with `fork_turns: "none"` or equivalent context isolation. Supply the same source-bound baseline view, preserving explicit human choices, constraints, amendments and relevant historical directions; label historical Agent suggestions as suggestions, not human commitments or current rankings. Exclude the moderator's current recommendation/ranking and peer outputs from round-1 inputs. Preserve the frozen original record and its source locators for checking facts and human commitments; do not attach an unfiltered transcript or recommendation-bearing record that defeats this isolation. Round 2 shares substantive discoveries while the moderator continues to withhold current recommendations and rankings. Recovery of an existing exploration reuses available role threads and the existing round record; it does not begin a fresh isolated round 1.

## Round progression

- Round 1: discover affected users/scenarios, desired outcomes, smallest viable directions, assumptions and unanswered boundaries independently.
- Round 2: exchange discoveries, cross-check sources and fill omissions; update the problem/question map. Delay recommendations and rankings through these first two rounds, while rejecting directions already disproved by evidence.
- Rounds 3–12: moderator dispatches current questions, explorers answer independently from the common record, cross-check relevant answers, then moderator reconciles and chooses next questions.

Default to 2–3 theme groups and 3–6 related questions total per round. Dependencies and actual uncertainty outrank that default: if only one or two valuable questions remain, ask those, never manufacture more. Only current-frontier questions can establish conclusions. Explicit conditional analysis may explore a later branch (“if export is selected…”), but does not select that branch.

One numbered round contains one question batch, the independent answers, necessary cross-check/clarification of those answers, and moderator synthesis. Newly unlocked substantive questions enter the next numbered round; do not hide unlimited iterations as clarification. Reuse the same two role threads when available and maintain the numbered record across recovery.

Each role answers its assigned questions with the conclusion, basis/conditions, strongest relevant counterexample or uncertainty, peer challenge where warranted, and changes to earlier conclusions. `no_material_delta` describes unchanged conclusions only; it cannot replace current answers or evidence. No valid new objection is a permissible result, not an instruction to manufacture dissent.

Cross-check especially: the peer's weakest material conclusion, an omitted outcome-changing scenario, a shared unsupported premise, and a fact that would change one's own judgment. The moderator prioritizes new evidence and high-impact uncertainty, not endless low-weight details or exhaustive implementation design.

## Cross-round correction

At each synthesis compare new answers against prior human constraints and important conclusions, including the claims' sources and conditions. Classify material changes:

1. **Actual contradiction:** conclusions cannot both hold under the same conditions. Surface the two claims and evidence, then target clarification/correction. If evidence cannot decide, preserve mutually exclusive assumptions and their consequences.
2. **Condition refinement:** retain the general statement and explicit exception; do not imply the exception waives a human constraint.
3. **Evidence-backed correction:** preserve the superseded claim, evidence and reason. The newest answer is not automatically correct. Correcting facts or removing unapproved overbuilding needs no new human gate.
4. **Human-intent change:** a proposal changing the human's confirmed outcome, boundary or material tradeoff is not a decision. Ask the human when needed and record their explicit amendment; peer consensus never overrides it.

Unresolved contradictions get priority but do not freeze independent themes. A finding closes through evidence, a revised candidate/control, a stated residual risk consistent with human authority, or an explicit outstanding human decision; “already considered” is not a disposition. Unresolved outcome-changing contradictions or risks cannot be called ready by relabeling them low impact.

New risks need a trigger, evidence/hypothesis label, link to the current user outcome, impact and smallest adequate control. They do not automatically become NEEDs or justify a platform. Keep hypothetical scope outside the commitment; apply the owning skill's Scope Ledger and PLATFORM_RECEIPT rules.

## End conditions and human decisions

After at least three rounds, exploration may stop when major current scenarios and high-impact boundaries have been challenged; decisive assumptions are sourced or explicitly unresolved; important contradictions have a disposition; viable options' costs, differences and non-goals are clear; and there is no remaining high-value question that further authorized analysis or available evidence can advance. A vague claim of consensus, two quiet rounds or `no_material_delta` is not proof of coverage.

Stopping exploration and being READY_FOR_INTENT are different. Human-only preferences can end Agent exploration but keep Requirement DRAFT until resolved. Investigate accessible facts rather than ask the human to rediscover them. At every substantive exit apply the owning skill's complete Decision Brief recipe, not only a remaining-choice menu; ask one necessary human decision at a time, not every autonomous round. No unresolved choice still requires an overview, not another confirmation gate. Do not treat a preference answer or brainstorming-record confirmation as final scope authorization.

Round 12 ends the current autonomous exploration budget. Preserve useful findings and unexamined consequences, not forced consensus. A human reply may settle a clear existing choice; re-challenge affected substantive boundaries within remaining rounds. At the cap, if fresh exploration is necessary, retain DRAFT and explain the need for a separately identified exploration for the human to decide. Explanation alone authorizes neither round 13 nor a reset. No automatic replay of all prior branches.

At each round show a short human-readable update: themes being tested, important correction/new boundary, and next focus or unresolved decision. Record round number, questions, consequential changes and remaining frontier in the Requirement evidence; do not expose private reasoning. Evaluate effectiveness through concrete challenges/corrections and bounded scope, not number of rounds.
