---
name: fastapi
version: 1.0.0
description: Guidance for diagnosing FastAPI/Starlette/Uvicorn-specific errors in incident logs.
author: AI Incident Investigator
triggers:
  keywords:
    - "uvicorn"
    - "starlette"
    - "fastapi"
    - "RequestValidationError"
    - "asgi"
  patterns:
    - "uvicorn\\.(error|access)"
    - "starlette\\."
    - "\\bASGI\\b"
---

# FastAPI

## When this applies

Logs from a FastAPI/Starlette/Uvicorn application: uvicorn access/error
logs, Pydantic request-validation errors, or ASGI-layer tracebacks.

## Guidance

- `RequestValidationError` / a Pydantic `ValidationError` on a request
  means the body/query/path didn't match the declared schema — check for
  an API contract mismatch with a client (a recent deploy on either side
  is the most common cause), not a server-side logic bug.
- A `500` with no application-level log line just above it, but a raw
  ASGI/Starlette traceback, usually means an unhandled exception escaped
  a route handler — look for the **last application-code frame** in the
  traceback (e.g. under `app/`), not the ASGI/Starlette internals that
  surround it.
- Repeated `asyncio.CancelledError`, request timeouts, or a sudden rise
  in latency across *all* endpoints (not just one) often indicates a
  blocking (synchronous) call inside an `async def` route handler — it
  stalls the whole event loop, not just the request that made the call.
- A spike in `4xx` responses is a client/contract issue; a spike in
  `5xx` responses is a server-side defect or dependency failure — don't
  conflate the two when judging severity or assigning an owner.
- Startup failures (`Application startup failed`) are almost always a
  dependency (database, config value, secret) not being ready yet, not
  an application code defect — check what runs in the `lifespan`/startup
  hook first.

## Examples

**Input:**

```
uvicorn.error: Exception in ASGI application
  File ".../fastapi/routing.py", line 212, in run_endpoint_function
  File "app/api/investigations.py", line 45, in create_investigation
    return await run_investigation(logs=request.logs, llm=llm)
  File "app/services/investigation_service.py", line 12, in run_investigation
LLMConfigurationError: ANTHROPIC_API_KEY is not set
```

**Guidance applied:** the last application frame
(`investigation_service.py`) is where the real fault originates, not the
routing/ASGI frames around it — this is a configuration problem, not a
code defect, and the fix is setting the missing environment variable.

**Input:**

```
INFO: 127.0.0.1:52344 - "POST /api/v1/investigations HTTP/1.1" 422 Unprocessable Entity
{"detail":[{"loc":["body","logs"],"msg":"String should have at least 1 character"}]}
```

**Guidance applied:** a `422` with a Pydantic `loc`/`msg` detail is
request validation working as intended, not an incident — the client
sent an empty field.
