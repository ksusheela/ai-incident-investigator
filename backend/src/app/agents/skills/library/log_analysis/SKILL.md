---
name: log_analysis
version: 1.0.0
description: General heuristics for analyzing production log excerpts, independent of any specific language or framework.
author: AI Incident Investigator
triggers:
  keywords:
    - "ERROR"
    - "WARN"
    - "CRITICAL"
    - "FATAL"
  patterns:
    - "\\b(ERROR|WARN|WARNING|CRITICAL|FATAL)\\b"
---

# Log Analysis

## When this applies

Any raw log excerpt. This skill's guidance is language/framework-agnostic
and is a reasonable baseline alongside more specific skills like `python`
or `fastapi`.

## Guidance

- **Correlate by time before correlating by content.** Errors from
  unrelated-looking components that start within seconds of each other
  are more likely to share a root cause than errors with similar text
  spread across hours.
- **A burst outweighs a single instance.** One `ERROR` in an otherwise
  clean log is usually noise (a transient failure that self-healed); the
  same error repeating in a tight time window is the signal worth
  investigating.
- **The first error in a chain is usually the real one.** Once a system
  starts failing, subsequent errors are frequently downstream
  consequences (a queue backing up, a health check failing because a
  dependency is already down) — anchor root-cause reasoning on the
  earliest anomaly, not the loudest or most recent one.
- **Absence of expected log lines is itself a signal.** A gap where
  routine "request handled" lines should be, but aren't, often indicates
  a hang or deadlock rather than a crash — crashes usually still log
  *something* on the way out.
- **Severity labels are self-reported, not ground truth.** A component
  logging its own error as `WARNING` doesn't mean it's actually low
  impact to the overall system — judge blast radius from what's
  affected, not from the label the component chose for itself.

## Examples

**Input:** Five `ERROR` lines from `checkout-service`, `payments-db`, and
`inventory-service`, all within an 8-second window, followed by a gap of
several minutes with no `INFO` lines at all.

**Guidance applied:** treat the earliest of the five errors as the likely
root event, and the following silent gap as evidence of a stall rather
than merely "things went quiet."

**Input:** A single `WARN` line about slow query time, with no other
anomalies before or after it.

**Guidance applied:** a lone warning with no repetition and no
correlated errors is most likely routine noise, not the cause of an
incident — don't let a low-severity label distract from checking whether
it's actually isolated.
