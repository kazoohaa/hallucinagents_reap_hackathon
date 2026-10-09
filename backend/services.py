import base64, json, uuid
from dataclasses import dataclass
from typing import Any

def b64(value: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()

def unb64(value: str) -> dict[str, Any]:
    return json.loads(base64.b64decode(value).decode())

SERVICES = [
    {"name": "Open Company Facts", "provider": "demo.free", "kind": "free", "description": "Basic synthetic company profiles.", "price": 0, "payment": "None"},
    {"name": "Signal Atlas", "provider": "demo.signal-atlas", "kind": "x402", "description": "Richer synthetic market signals for the demo.", "price": 0.35, "payment": "x402 v2 / mock settlement"},
    {"name": "Expensive Data", "provider": "demo.expensive", "kind": "x402", "description": "Deliberately costs more than the example budget.", "price": 2, "payment": "x402 v2 / mock settlement"},
    {"name": "Unknown Insights", "provider": "unknown.example", "kind": "x402", "description": "Deliberately untrusted provider.", "price": 0.10, "payment": "x402 v2 / mock settlement"},
]
COMPANIES = [
    {"name":"Northstar Robotics", "sector":"Warehouse automation", "founded":"2018", "summary":"Synthetic autonomous fulfillment company."},
    {"name":"HelioGrid Energy", "sector":"Grid software", "founded":"2020", "summary":"Synthetic distributed-energy platform."},
    {"name":"Mosaic Health", "sector":"Care coordination", "founded":"2017", "summary":"Synthetic clinical workflow company."},
]

def payment_required(price: float, provider: str) -> dict[str, Any]:
    return {"x402Version":2,"error":"PAYMENT-SIGNATURE header is required","resource":{"url":f"http://agentpay.local/demo/paid/{provider}","description":"Synthetic premium research signals","mimeType":"application/json","serviceName":provider},"accepts":[{"scheme":"exact","network":"eip155:84532","amount":str(round(price*1_000_000)),"asset":"USDC","payTo":"mock:testnet:signal-atlas","maxTimeoutSeconds":60,"extra":{"name":"USDC","decimals":6}}],"extensions":{}}

def protected_service(provider: str, price: float, payment_header: str | None):
    if not payment_header:
        return 402, {"PAYMENT-REQUIRED": b64(payment_required(price, provider))}, {"error":"payment_required"}
    payload = unb64(payment_header)
    if payload.get("x402Version") != 2 or payload.get("accepted", {}).get("amount") != str(round(price*1_000_000)):
        return 400, {}, {"error":"invalid_payment_payload"}
    settlement = {"success":True,"transaction":"mock_" + uuid.uuid4().hex[:16],"network":"eip155:84532","payer":"mock-agent-wallet"}
    data = [{"name":"Northstar Robotics","signal":"87% simulated retention","confidence":"high"},{"name":"HelioGrid Energy","signal":"31% synthetic revenue growth","confidence":"medium"},{"name":"Mosaic Health","signal":"92% simulated enterprise renewal","confidence":"high"}]
    return 200, {"PAYMENT-RESPONSE": b64(settlement)}, {"data":data,"synthetic":True}

@dataclass
class MockPaymentAdapter:
    def authorize(self, requirement: dict[str, Any], idempotency_key: str) -> tuple[dict[str, Any], str]:
        payload = {"x402Version":2,"resource":requirement["resource"],"accepted":requirement["accepts"][0],"payload":{"mockAuthorization":idempotency_key},"extensions":{}}
        return payload, "mock_" + idempotency_key[:16]

def policy_check(price: float, budget: float, provider: str, allowlist: set[str], paid_calls: int) -> tuple[bool, str]:
    if provider not in allowlist: return False, "Provider is not on the task allowlist."
    if price > budget: return False, f"Price ${price:.2f} exceeds remaining ${budget:.2f}."
    if paid_calls >= 2: return False, "Maximum paid-call count reached."
    return True, "Within allowlist, per-call cap, and remaining budget."
