---
name: privacy-coding-rule
description: Use when a repository or organization supplies internal privacy, data-handling, logging, or approved-destination requirements for implementation or review.
---

# 组织隐私编码规则

This skill is the home for the organization's internal privacy and data-handling coding rules. Its source of truth is the applicable organization policy, repository policy, and approved data-classification standard—not generic framework advice.

## Apply the supplied policy faithfully

Before handling personal data, identifiers, content, credentials, telemetry, test fixtures, exports, or external integrations:

1. Locate the applicable internal rule and identify the data classification, allowed purpose, retention, and owner.
2. Use only approved destinations, storage classes, logging/telemetry fields, and redaction methods.
3. Preserve required consent, access-control, audit, deletion, residency, or review gates.
4. Record the policy reference and the implementation evidence required by the repository.

Do not invent or weaken a policy. If the applicable rule is absent, contradictory, or cannot be interpreted safely, stop and ask the policy owner or human engineer rather than substituting a generic best practice.

## Boundary checklist

Assess the complete data path: collection, validation, in-memory transformation, logs/traces/metrics, queues, caches, persistence, exports, test data, debugging tools, and third-party calls. A redaction at one boundary does not make downstream copies safe.

## Writing organization rules here

Keep rules concrete and verifiable: name the data class, permitted purpose, approved destinations, prohibited fields, retention/deletion behavior, required audit evidence, and escalation owner. Link to the authoritative policy rather than copying a broad privacy manual. Update this skill only when the organization rule itself changes.

## Review prompts

- Which internal policy governs this data path, and what evidence proves compliance?
- Does every destination remain approved after retries, failures, debugging, and test execution?
- Could a log, trace, fixture, error, or support artifact reintroduce protected data?
- Is this a policy ambiguity that requires escalation rather than an implementation choice?
