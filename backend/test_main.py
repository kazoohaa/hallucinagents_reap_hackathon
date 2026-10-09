from fastapi.testclient import TestClient
from backend.main import app

client=TestClient(app)
def run(scenario="success", permission=True):
    return client.post("/api/tasks/run",json={"prompt":"Research three companies and create a comparison.","budget_usd":1,"permission_to_spend":permission,"scenario":scenario})
def test_paid_vertical_slice():
    body=run().json(); assert body["spent"] == .35; assert any(x["kind"]=="http_402" for x in body["ledger"]); assert "Premium" in body["report"]
def test_budget_rejection():
    body=run("budget_exceeded").json(); assert body["spent"] == 0; assert any(x["status"]=="rejected" for x in body["ledger"])
def test_untrusted_rejection():
    body=run("untrusted").json(); assert body["spent"] == 0
def test_permission_required():
    body=run(permission=False).json(); assert body["spent"] == 0
def test_demo_resource_exposes_x402_headers():
    response=client.get("/demo/paid/demo.signal-atlas"); assert response.status_code == 402; assert "payment-required" in response.headers
def test_reap_status_never_exposes_secret():
    response=client.get("/api/reap/status"); assert response.status_code == 200; assert "api_key" not in response.text.lower()
