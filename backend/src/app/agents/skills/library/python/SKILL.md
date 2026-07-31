---
name: python
version: 1.0.0
description: Guidance for diagnosing Python exceptions and stack traces found in incident logs.
author: AI Incident Investigator
triggers:
  keywords:
    - "Traceback (most recent call last)"
    - "Error:"
    - "Exception:"
  patterns:
    - "Traceback \\(most recent call last\\):"
    - "\\b\\w+(Error|Exception)\\b\\s*:"
---

# Python

## When this applies

Logs containing a Python traceback, or an exception name such as
`ValueError`, `KeyError`, `ConnectionError`, or a custom `*Error`/
`*Exception` class.

## Guidance

- The **last line** of a traceback (`ExceptionType: message`) names the
  immediate failure; the **frames above it**, read bottom-to-top, show
  the call path that led there. The deepest application frame is usually
  closest to the actual defect — not necessarily the entry point that
  started the request.
- Common categories and what they usually indicate:
  - `KeyError` / `AttributeError` / `TypeError` — unexpected or missing
    data shape, often from an upstream API/response change rather than a
    local bug.
  - `ConnectionError` / `TimeoutError` / `OSError` — a downstream
    dependency (database, cache, external API) is slow, unreachable, or
    a connection pool is exhausted.
  - `MemoryError` — resource exhaustion, often the tail end of a slow
    memory leak rather than a sudden event.
  - A custom exception class (e.g. `PaymentDeclinedError`) usually
    encodes an application-level business rule, not an infrastructure
    fault — treat it as expected-but-unhandled unless it's unusually
    frequent.
- If the same exception type recurs across otherwise-unrelated request
  paths, suspect a shared dependency (a client library, a config value,
  a shared cache) rather than a defect local to one code path.
- Frames inside third-party library code (e.g. under `site-packages`)
  are rarely where the actual bug lives — the fix is almost always in
  how application code calls that library, not in the library itself.

## Examples

**Input:**

```
Traceback (most recent call last):
  File "app.py", line 42, in handle_request
    result = process(payload)
  File "app.py", line 17, in process
    return 1 / count
ZeroDivisionError: division by zero
```

**Guidance applied:** `count` reached zero somewhere upstream of
`process()` — look at whatever sets `count` (likely a batch size or a
divisor derived from user input) for a missing validation, rather than at
the division line itself.

**Input:**

```
requests.exceptions.ConnectionError: HTTPConnectionPool(host='payments-db', port=5432):
Max retries exceeded with url: /health (Caused by NewConnectionError(...))
```

**Guidance applied:** this is a downstream-dependency failure
(`payments-db` unreachable), not an application code defect — the
investigation should focus on `payments-db`'s availability/network path,
not on the code that made the request.
