# Project Principles

X Reach is the X/Twitter-only execution layer for agent-assisted research. It is not a general social scraper, a search router, a dashboard product, or a final analysis system.

The project exists to let agents and host projects collect X posts in a reproducible, inspectable way, reduce obvious noise, produce useful candidate evidence, and hand off stable machine-readable artifacts.

## North Star

Optimize for high-signal X evidence that an external caller can trust, inspect, rerun, and reinterpret.

When tradeoffs arise, prefer stable contracts, deterministic processing, explicit caller intent, and artifact quality over hidden automation or broad product ownership.

## Ownership Boundaries

X Reach owns:

- the `twitter` channel contract, readiness checks, and operation metadata;
- read-only X/Twitter collection through the CLI and `XReachClient`;
- mission spec normalization and execution for broad collection jobs;
- raw, canonical, and curated artifact layers;
- deterministic noise reduction, dedupe, candidate scoring, and diversity constraints;
- checkpoint/resume behavior, partial results, ledgers, schemas, and diagnostics;
- opt-in judge contracts that can fall back to deterministic records.

The caller owns:

- whether X/Twitter is the right source for the task;
- objective, queries, time range, language, geography, scope, and budget;
- topic-specific noise rules, coverage topics, judge criteria, and domain assumptions;
- final interpretation, synthesis, selection, publication, scheduling, and downstream UI.

This split should stay visible in code and docs. X Reach can make collection easier and cleaner, but it should not silently decide what the investigation means.

## Design Rules

### JSON First

Public outputs must remain stable, schema-aware, and suitable for downstream automation. Human-readable text is allowed as a companion view, not as the only contract.

### Mission Spec First For Broad Runs

Use `x-reach collect --json` for narrow collection and smoke checks. Use `x-reach collect --spec` when the run has multiple queries, artifact needs, budget constraints, coverage requirements, or resume expectations.

### Deterministic Before LLM

Prefer parsing, explicit filters, dedupe, rule-based scoring, and neutral diagnostics before any model call. LLM/VLM judgment is acceptable only as an opt-in bounded layer after deterministic narrowing, with auditable fallback behavior.

### Preserve Raw / Canonical / Curated Layers

Keep acquisition data, normalized records, and candidate evidence separate. This lets callers revisit older runs when filters, scoring, or downstream analysis changes.

### Theme Fit Without Theme Lock-In

Support caller-declared objectives, query terms, exclude rules, coverage topics, and judge intent. Do not bake restaurant, product, incident, political, OSS, entertainment, or any other domain-specific assumptions into general defaults.

### Quality Is Evidence Utility

Quality is not popularity. Engagement may be a weak diagnostic, but useful evidence is more about topic fit, substance, first-hand or observable claims, specificity, dedupe behavior, and diversity across authors, threads, URLs, topics, and time.

### Scale Is A Design Input

Large runs should be resumable, shardable, budgeted, and observable from the start. Avoid designs that work only for a few manual searches and collapse when the caller asks for hundreds of posts.

### Compact By Default

Broad discovery should keep artifacts small unless the caller explicitly asks for fuller payloads. Deep reads and full raw retention belong behind deliberate opt-in controls.

### X-Specific, Not X-Only Thinking

This repository intentionally ships only the `twitter` channel. X-specific details belong in adapters and channel contracts, while common primitives such as mission specs, ledgers, candidate planning, and schemas should stay reusable inside the X workflow.

### Extend Existing Surfaces

Prefer improving `collect`, `collect --spec`, `batch`, `ledger`, `plan candidates`, `doctor`, `channels`, schemas, or bundled skills over adding parallel commands or hidden workflows.

## Feature Adoption Gate

Adopt a change when it:

- directly improves X post collection, candidate quality, diagnostics, artifacts, or handoff;
- keeps caller intent explicit and machine-readable;
- improves reproducibility, observability, or resume safety;
- reduces obvious noise without hiding important raw signals;
- works for narrow and broad runs, or is clearly scoped to one of them.

Reject or defer a change when it:

- silently expands scope, retries indefinitely, deep-reads, ranks final meaning, summarizes, posts, or routes for the caller;
- hides topic-specific assumptions in global defaults;
- adds opaque LLM/VLM decisions before deterministic narrowing;
- destabilizes JSON schemas, CLI contracts, or packaged skill guidance;
- duplicates an existing surface without reducing real friction.

When a proposal mixes a useful primitive with risky automation, keep the primitive and reject or defer the policy layer.

## Naming And Interface Conventions

- Product name: `X Reach`.
- CLI command: `x-reach`.
- Primary Python package: `x_reach`.
- Stable channel name: `twitter`.
- Compatibility package: `agent_reach`, only as a thin shim.
- Broad declarative execution: `mission spec`.
- Evidence layers: `raw`, `canonical`, and `curated` or `ranked` where the runtime artifact already uses that name.

Avoid names that imply X Reach is a final analyst, scheduler, publisher, or generic multi-network agent.

## Implementation Priorities

When design or implementation choices conflict, use this order:

1. Improve X collection result quality.
2. Keep large runs from becoming fragile.
3. Make agent and downstream usage stable and predictable.
4. Improve reproducibility and auditability.
5. Preserve broad topic usefulness without hard-coded domain policy.
6. Keep caller control explicit.
7. Minimize implementation cost and maintenance weight.

If an item scores clearly on a higher priority, consider it before rejecting it for a lower-priority cost. If it weakens a higher priority, keep it out even when it looks convenient.

## Done Definition

A feature is done when it can be used as decision material, not merely when the code path exists.

For public behavior, that usually means:

- schemas and JSON outputs are clear;
- narrow and representative broad cases have tests;
- restart or partial-failure behavior is known when the feature touches jobs;
- dropped or transformed data leaves diagnostics;
- docs and bundled skills explain the boundary without taking over caller judgment.
