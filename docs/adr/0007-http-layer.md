# 0007 — Outbound HTTP: httpx2, a limiter per source, an opt-in cache

- **Status:** Accepted
- **Date:** 2026-11-04
- **Task:** 9 (HTTP layer)

## Context

Task 9 builds the shared client for academic sources: a per-source rate limiter, exponential back-off and a response cache. The plan names `httpx`, `hishel` and `tenacity`. ADR 0002 left the client choice open: Starlette's test client has moved to `httpx2`, and `httpx` has had no release since December 2024.

Two project rules shape the design. API keys must never reach the database or logs (rule 7), and `hishel` stores requests, including their headers, next to responses. A search run must also record what a source says at that moment, or the systematic record is false.

## Decision

- **`httpx2` for outbound HTTP** *(deviation from plan, approved by the owner)*. Production and tests use one client package. `hishel` 1.4 supports it through its `httpx2` extra.
- **`tez.shared.http.HttpClient` is the only way out.** A `SourcePolicy` declared by each provider sets the rate, timeout, attempts and back-off.
- **Rate limiter:** our own 20-line spacing limiter rather than another dependency. Idle time builds no burst, because sources state their limits per second. Each source has one limiter.
- **Retries** (`tenacity`): 429, 500, 502, 503, 504, timeouts and connection errors. Other 4xx responses are not retried.
  - The wait is the larger of the exponential back-off and `Retry-After` (seconds or HTTP date).
  - A 429 also pushes back that source's limiter, so concurrent requests to it hold too.
  - A `Retry-After` beyond `max_retry_after_seconds` (default 120) means the quota is gone for now: it fails at once with the wait in its params.
  - `on_wait` reports each wait, for the "rate limited" countdown on the source chip (design 4.2).
- **Errors** are `TezError`s: `source.rate_limited`, `source.timeout`, `source.network`, `source.unavailable`, `source.rejected`, always with `source` in the params.
- **The cache is opt-in per call** through `cache_ttl`. Without it the cache is neither read nor written. Searches pass none; metadata lookups can. Only 200 responses are stored.
- **API keys are added below the cache,** in a transport matched by host. The cache and the client's logging never see them, and a redirect to another host does not carry them.
- **The client's per-request log line is turned off,** because source URLs can carry the user's e-mail (polite-pool parameter).
- **A broken cache file is logged and ignored;** requests continue without a cache (rule 5).

## Consequences

- The cache file belongs in the library folder (`.tez/http-cache.sqlite`, rule 1). Task 13 wires this when it creates the client.
- A provider that sends its key as a query parameter would put it in the cache key and the stored URL. Such a provider must use a header, or the secret transport must learn to add parameters (checked in Task 11).
- The async SQLite storage runs its connection on a worker thread, so `HttpClient` must be closed; the tests run with `ResourceWarning` as an error.
- New dependencies: `httpx2` (BSD-3-Clause, moved from dev to runtime), `hishel` (BSD-3-Clause), `tenacity` (Apache-2.0), and through them `anysqlite` (BSD-3-Clause) and `msgpack` (Apache-2.0).
