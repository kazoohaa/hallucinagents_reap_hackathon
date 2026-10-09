"""Backend-only client for Reap Agentic Payments sandbox.

No secret is returned from this module. Calls occur only when an API route invokes it.
"""
import os
import uuid
from pathlib import Path
import httpx

def load_local_env() -> None:
    path = Path("env.local")
    if not path.exists(): return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

class ReapClient:
    def __init__(self):
        self.api_key = os.getenv("REAP_API_KEY", "")
        self.base_url = os.getenv("REAP_BASE_URL", "https://sandbox.api.reap.global").rstrip("/")
        self.version = os.getenv("REAP_VERSION", "2025-02-14")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self, idempotency: bool = False, simulate_complete: bool = False) -> dict[str, str]:
        if not self.configured: raise RuntimeError("REAP_API_KEY is missing from env.local")
        headers = {"Authorization": f"Bearer {self.api_key}", "Reap-Version": self.version, "Content-Type": "application/json"}
        if idempotency: headers["Idempotency-Key"] = str(uuid.uuid4())
        if simulate_complete: headers["X-Simulate-Checkout"] = "COMPLETED"
        return headers

    def request(self, method: str, path: str, payload: dict | None = None, *, idempotency=False, simulate_complete=False) -> dict:
        try:
            response = httpx.request(method, f"{self.base_url}{path}", headers=self._headers(idempotency, simulate_complete), json=payload, timeout=20)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            # Preserve provider error detail without leaking headers or API key.
            try: detail = exc.response.json()
            except ValueError: detail = {"message": exc.response.text[:500]}
            raise ValueError({"status": exc.response.status_code, "reap_error": detail}) from exc
        except httpx.RequestError as exc:
            raise ValueError({"status": 503, "reap_error": {"message": "Reap sandbox is unreachable", "detail": str(exc)}}) from exc

    def create_external_enrollment(self, owner_id: str, email: str, return_url: str) -> dict:
        return self.request("POST", "/agentic/enrollments", {"source":"EXTERNAL", "owner":{"type":"CLIENT_REFERENCE","id":owner_id,"email":email}, "presentation":{"type":"REDIRECT","returnUrl":return_url}}, idempotency=True)

    def enrollment(self, enrollment_id: str) -> dict:
        return self.request("GET", f"/agentic/enrollments/{enrollment_id}")

    def search(self, query: str, budget_usd: float) -> dict:
        return self.request("POST", "/agentic/products/search", {"query":query,"context":{"country":"US","currency":"USD"},"filters":{"price":{"min":"0","max":str(budget_usd)},"availability":"AVAILABLE_ONLY"},"pagination":{"limit":10}})

    def quote(self, variant_id: str, email: str) -> dict:
        return self.request("POST", "/agentic/quotes", {"items":[{"variantId":variant_id,"quantity":1}],"email":email}, idempotency=True)

    def checkout(self, quote_id: str, enrollment_id: str, return_url: str, simulate_complete: bool = True) -> dict:
        return self.request("POST", "/agentic/checkouts", {"quoteId":quote_id,"enrollmentId":enrollment_id,"presentation":{"type":"REDIRECT","returnUrl":return_url}}, idempotency=True, simulate_complete=simulate_complete)

    def checkout_status(self, checkout_id: str) -> dict:
        return self.request("GET", f"/agentic/checkouts/{checkout_id}")
