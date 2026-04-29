# Backend scripts

Throwaway / one-off scripts that aren't part of the test suite or the
application. Run inside the backend container:

```bash
docker compose exec backend python scripts/<name>.py
```

## Yahoo Finance probes

These count actual upstream HTTP requests by monkey-patching
`curl_cffi.requests.Session.request`. They make real network calls to
`query2.finance.yahoo.com` and are not safe to run in CI.

- `probe_yahoo_calls.py` — measures HTTP fan-out per `YahooClient`
  method on a single representative symbol. Useful for verifying that
  endpoint changes (e.g. swapping `ticker.price` for `ticker.quotes`)
  actually reduce upstream traffic.
- `probe_yahoo_session_reuse.py` — verifies whether yahooquery's
  consent/crumb bootstrap (3 setup HTTP calls) is paid per `_call`
  invocation or amortised across them. Used to validate the session-
  reuse behaviour in `YahooClient._ticker()`.
