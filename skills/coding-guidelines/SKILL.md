---
name: coding-guidelines
description: Use when writing, reviewing, or refactoring code to avoid speculative abstractions, premature platformization, scope creep, and unverifiable changes.
license: MIT
---

# Coding Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. The original four principles are informed by [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### Evidence-Driven Abstraction

**Default to local, explicit, linear orchestration. An abstraction must solve a current problem, not decorate a possible future.**

For a small feature, an entrypoint may validate input, call named domain services in business order, and assemble the response directly. Several steps do not make a framework necessary.

Add an interface, factory, registry, pipeline, generic context, strategy layer, or shared execution framework only with current evidence: two current independent consumers share a meaningful invariant; the approved requirement needs multiple implementations or runtime variation now; an external protocol/vendor/security/transaction boundary needs isolation; or the current flow is a real state machine whose error or rollback behavior direct code hides.

Future flexibility is not evidence. A single caller, hypothetical plugin, imagined second implementation, or architectural symmetry does not justify a layer. Treat Pipeline, Context, Registry, Executor, Manager, or Factory as warning names; prefer a narrow domain name and direct code when both are clear.

Before adding an abstraction, write an abstraction receipt: current repetition, variation, or boundary; current consumers; why direct local code is inadequate; and why the added complexity pays for itself. Without that receipt, keep it direct and extract when a second real use arrives.

### Review for Premature Platformization

Ask whether each new layer has an abstraction receipt, whether direct calls to existing domain services would make the business order clearer, and whether configuration, extension points, registries, base classes, or generic containers have a current consumer. Classify unsupported frameworking as `Over-abstraction / Premature platformization`; recommend inlining it unless current evidence exists. Readable sequencing is often the correct design.

## 3. Reliability Boundaries

Use risk-based reliability boundaries, not a universal style checklist. Identify the actual boundary before adding validation, error handling, wrapping, logging, or a new type.

- At an untrusted input or execution boundary—HTTP, MQ, file, CLI, webhook, SQL, shell, path, template, or deserialization—validate/normalize input and use safe APIs or parameterization.
- At a trusted boundary between typed internal components, state and preserve the invariant. Do not add defensive checks merely to make every access optional; that can hide a defect.
- Keep secrets, tokens, credentials, and PII out of logs, errors, telemetry, fixtures, and debug output.
- Make resource ownership explicit and use scoped cleanup. Do not silently discard asynchronous failures.
- Follow the language and repository convention for comparisons. Use guard clauses when they clarify the normal path; do not impose Yoda conditions or split cohesive code solely to meet a metric.

Function length, parameter count, nesting, broad dynamic payloads, and repeated conditionals are review signals, not an automatic extraction rule. Extract only for a current responsibility boundary, testability, or readability problem.

For shared mutable state, ownership transfer, lock ordering, cancellation, background lifecycle, or cross-thread/async boundaries, invoke `concurrent-design-review`. This guideline does not replace its independent review and coverage decision.

## 4. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 5. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
