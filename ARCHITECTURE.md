# Architecture

`Vue` is the intended production client stack; this MVP uses a dependency-free static dashboard so it runs immediately, while preserving a JSON API boundary for a Vue 3 client. FastAPI owns all policy and payment-sensitive logic; the browser only submits task permissions and renders state.

## Vertical slice

1. The orchestrator obtains free synthetic company facts.
2. It calls a registry-selected local protected service.
3. The service responds with an x402 v2 `PAYMENT-REQUIRED` base64 header.
4. The backend parses terms, enforces allowlist, budget, call limit, and explicit permission, then reserves funds.
5. `MockPaymentAdapter` generates an x402-shaped `PAYMENT-SIGNATURE`; no token is signed or settled.
6. The retry returns synthetic data and an x402 `PAYMENT-RESPONSE`; the ledger commits spend only then.

The local protocol headers follow the v2 HTTP transport: `PAYMENT-REQUIRED`, `PAYMENT-SIGNATURE`, and `PAYMENT-RESPONSE`. Production must use the official SDK/scheme-specific signer, validate every requirement/resource binding, and reconcile uncertain settlement before retrying.

## Reap sandbox commerce

The backend integrates Reap's sandbox commerce flow: external enrollment, catalog search, quote creation, hosted checkout, and status reads. These calls are separate from the local x402 demo. A hosted Reap approval remains required before a payment method can be used, and the app never receives card data.

There is still no x402 settlement bridge: `MockPaymentAdapter` is deliberately local-only. Do not describe its synthetic transaction references or `PAYMENT-SIGNATURE` payload as a Reap, on-chain, or production payment.
