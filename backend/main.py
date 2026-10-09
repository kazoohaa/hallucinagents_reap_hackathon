import json, os, uuid
from fastapi import FastAPI, HTTPException, Header, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .database import Base, SessionLocal, engine
from .models import Task, LedgerEntry
from .services import COMPANIES, SERVICES, MockPaymentAdapter, protected_service, unb64, b64, policy_check
from .reap import ReapClient, load_local_env

load_local_env()
Base.metadata.create_all(engine)
app = FastAPI(title="AgentPay MVP")

class RunRequest(BaseModel):
    prompt: str = Field(min_length=4)
    budget_usd: float = Field(gt=0, le=10)
    permission_to_spend: bool = False
    scenario: str = "success"

class ReapEnrollmentRequest(BaseModel):
    owner_id: str = Field(default="customer", min_length=1)
    email: str
    return_url: str | None = None

class ReapSearchRequest(BaseModel):
    query: str = Field(min_length=2)
    budget_usd: float = Field(gt=0)

class ReapQuoteRequest(BaseModel):
    variant_id: str
    email: str

class ReapCheckoutRequest(BaseModel):
    quote_id: str
    enrollment_id: str
    return_url: str | None = None
    simulate_complete: bool = True

def return_url(value: str | None) -> str:
    """Keep deployment routing in backend config; never make customers paste URLs."""
    configured = value or os.getenv("PUBLIC_RETURN_URL", "")
    if not configured.startswith("https://"):
        raise HTTPException(503, "PUBLIC_RETURN_URL must be a public HTTPS URL ending in /reap/return")
    return configured

def reap_call(fn):
    try: return fn()
    except RuntimeError as exc: raise HTTPException(503, str(exc))
    except ValueError as exc: raise HTTPException(502, exc.args[0])

def entry(db, task_id, kind, status, detail, provider="", amount=0, tx=""):
    db.add(LedgerEntry(task_id=task_id,kind=kind,status=status,detail=detail,provider=provider,amount_usd=amount,transaction_ref=tx)); db.commit()

@app.get("/api/services")
def services(): return SERVICES

@app.get("/reap/return", response_class=Response)
def reap_return():
    """Local landing page for a Reap hosted enrollment/approval redirect."""
    return Response("""<!doctype html><title>ReapPay return</title><body style='font-family:system-ui;background:#070b14;color:#e2e8f0;padding:3rem'><h1>Returned from Reap</h1><p>Return to Postman and read the enrollment or checkout status. A browser redirect alone does not prove the payment method is active.</p></body>""", media_type="text/html")

@app.get("/api/reap/status")
def reap_status():
    client = ReapClient()
    return {"configured": client.configured, "checkout_ready": bool(os.getenv("PUBLIC_RETURN_URL", "").startswith("https://")), "base_url": client.base_url, "version": client.version, "mode": "sandbox" if "sandbox" in client.base_url else "non-sandbox"}

@app.post("/api/reap/enrollments")
def reap_enrollment(body: ReapEnrollmentRequest):
    """Creates enrollment; redirect user to response.nextAction.url, never handle card data here."""
    return reap_call(lambda: ReapClient().create_external_enrollment(body.owner_id, body.email, return_url(body.return_url)))

@app.get("/api/reap/enrollments/{enrollment_id}")
def reap_enrollment_status(enrollment_id: str): return reap_call(lambda: ReapClient().enrollment(enrollment_id))

@app.post("/api/reap/products/search")
def reap_search(body: ReapSearchRequest): return reap_call(lambda: ReapClient().search(body.query, body.budget_usd))

@app.post("/api/reap/quotes")
def reap_quote(body: ReapQuoteRequest): return reap_call(lambda: ReapClient().quote(body.variant_id, body.email))

@app.post("/api/reap/checkouts")
def reap_checkout(body: ReapCheckoutRequest):
    """Sandbox simulation only by default. Production requires hosted Reap approval instead."""
    return reap_call(lambda: ReapClient().checkout(body.quote_id, body.enrollment_id, return_url(body.return_url), body.simulate_complete))

@app.get("/api/reap/checkouts/{checkout_id}")
def reap_checkout_status(checkout_id: str): return reap_call(lambda: ReapClient().checkout_status(checkout_id))

@app.get("/demo/paid/{provider}")
def paid_demo(provider: str, payment_signature: str | None = Header(default=None, alias="PAYMENT-SIGNATURE")):
    """Inspectable local x402 v2-shaped protected resource; strictly synthetic/mock."""
    match = next((service for service in SERVICES if service["provider"] == provider), None)
    if not match or match["kind"] != "x402":
        raise HTTPException(404, "Protected demo provider not found")
    status, headers, body = protected_service(provider, match["price"], payment_signature)
    return Response(content=json.dumps(body), status_code=status, headers=headers, media_type="application/json")

@app.get("/api/tasks/{task_id}")
def task_detail(task_id: int):
    db=SessionLocal(); task=db.get(Task, task_id)
    if not task: raise HTTPException(404,"Task not found")
    rows=db.query(LedgerEntry).filter_by(task_id=task_id).order_by(LedgerEntry.id).all()
    return {"id":task.id,"prompt":task.prompt,"budget_usd":task.budget_usd,"spent":task.total_spent,"reserved":task.reserved,"remaining":round(task.budget_usd-task.total_spent-task.reserved,2),"status":task.status,"report":task.report,"ledger":[{"kind":r.kind,"status":r.status,"detail":r.detail,"provider":r.provider,"amount_usd":r.amount_usd,"transaction_ref":r.transaction_ref} for r in rows]}

@app.post("/api/tasks/run")
def run_task(request: RunRequest):
    db=SessionLocal(); task=Task(prompt=request.prompt,budget_usd=request.budget_usd,status="running"); db.add(task); db.commit(); db.refresh(task)
    entry(db,task.id,"planning","complete","Planned free company facts plus premium signals only if policy permits.")
    entry(db,task.id,"service_request","complete","Free source returned basic synthetic company profiles.","demo.free")
    chosen={"success":("demo.signal-atlas",.35),"budget_exceeded":("demo.expensive",2.0),"untrusted":("unknown.example",.10),"insufficient_value":("demo.signal-atlas",.35)}.get(request.scenario,("demo.signal-atlas",.35))
    provider, price=chosen
    if request.scenario == "insufficient_value":
        entry(db,task.id,"payment_decision","skipped","Premium source would add little value for this request; used free data.",provider,price)
        task.report=report(False); task.status="complete"; db.commit(); return task_detail(task.id)
    code,headers,_=protected_service(provider,price,None)
    req=unb64(headers["PAYMENT-REQUIRED"])
    entry(db,task.id,"http_402","detected",f"Parsed x402 v2 PAYMENT-REQUIRED header for ${price:.2f}.",provider,price)
    allowed,reason=policy_check(price,request.budget_usd,provider,{"demo.signal-atlas","demo.expensive"},0)
    if not request.permission_to_spend: allowed,reason=False,"User did not grant autonomous spending permission."
    entry(db,task.id,"policy_check","approved" if allowed else "rejected",reason,provider,price)
    if not allowed:
        task.report=report(False); task.status="complete"; db.commit(); return task_detail(task.id)
    task.reserved=price; db.commit(); entry(db,task.id,"funds_reserved","complete","Reserved funds before settlement to prevent double spend.",provider,price)
    payload,tx=MockPaymentAdapter().authorize(req,uuid.uuid4().hex)
    entry(db,task.id,"payment","mock_authorized","Mock adapter created an x402 payment payload; no blockchain settlement occurred.",provider,price,tx)
    code,headers,data=protected_service(provider,price,b64(payload))
    if code != 200: task.status="pending_reconciliation"; db.commit(); return task_detail(task.id)
    settlement=unb64(headers["PAYMENT-RESPONSE"]); task.reserved=0; task.total_spent=price; task.report=report(True); task.status="complete"; db.commit()
    entry(db,task.id,"service_response","complete","Premium synthetic signals received after mock payment retry.",provider,price,settlement["transaction"])
    return task_detail(task.id)

def report(premium: bool):
    rows=[]
    for c in COMPANIES:
        note={"Northstar Robotics":"Best fit for operations-led growth.","HelioGrid Energy":"Strong momentum but lower signal confidence.","Mosaic Health":"Most resilient synthetic renewal profile."}[c["name"]]
        rows.append(f"{c['name']} — {c['sector']} ({c['founded']}): {note}")
    label="Premium synthetic signals were incorporated." if premium else "Comparison uses free synthetic information only."
    return "Synthetic demonstration report. " + label + "\n\n" + "\n".join(rows)

@app.get("/", include_in_schema=False)
def live_dashboard():
    return FileResponse("frontend/live.html")

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
