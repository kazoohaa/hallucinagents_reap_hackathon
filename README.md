# AgentPay MVP

A sandbox-only autonomous service-consumption demo for the Reap × 65labs hackathon. It demonstrates an agent requesting a local paid API, parsing x402 v2-style HTTP 402 terms, applying deterministic policy, executing a **mock** authorization, retrying, and displaying an auditable ledger.

## Run

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8002
```

Open http://127.0.0.1:8002. The UI includes repeatable happy-path, budget, untrusted-provider, and insufficient-value scenarios.

## Test

```powershell
python -m pytest backend/test_main.py -q
```

## What is real vs. mocked

The FastAPI API, SQLite ledger, policy enforcement, local 402/retry control flow, and base64 x402 v2 HTTP header handling are working. The separate Reap catalog, enrollment, quote, hosted-checkout, and status routes call Reap's sandbox API. Company data, the local protected providers, x402 authorization, transaction references, and x402 settlement remain synthetic/mock; there is no wallet, private key, official x402 SDK, or testnet transaction.

See [ARCHITECTURE.md](ARCHITECTURE.md) for boundaries and Reap/Payward uncertainty. Environment variables are documented in `.env.example`.

## Reap sandbox integration

Put `REAP_API_KEY`, `REAP_BASE_URL`, `REAP_VERSION`, and a public HTTPS `PUBLIC_RETURN_URL` ending in `/reap/return` in `env.local`; it is ignored by Git and loaded only by the backend. `GET /api/reap/status` confirms configuration without exposing the key. The customer dashboard lets a buyer search, begin Reap's hosted enrollment approval, then create a quote and sandbox checkout after that approval is active. The backend exposes the same enrollment, catalog search, quote, checkout, and checkout-status routes under `/api/reap/`. In sandbox, `simulate_complete` defaults to `true` and sends Reap's documented sandbox-only simulation header.

Import `postman/ReapPay-Sandbox.postman_collection.json` into Postman for the full enrollment → search → quote → checkout flow. Set its `publicReturnUrl` collection variable to an HTTPS URL that routes to this app's `/reap/return` endpoint; Reap rejects plain `http://127.0.0.1` return URLs. Open the hosted URL returned from enrollment and complete the required approval before creating a checkout.
