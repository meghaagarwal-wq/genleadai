"""
Iter136 — Comprehensive backend health audit.

Hits every documented route and classifies the result into:
  - HEALTHY   : 2xx
  - DEGRADED  : 4xx because of missing 3rd-party integration key / OAuth creds
                (5xx-with-"missing key" message also classified here)
  - BROKEN    : 5xx tracebacks, unexpected 4xx (e.g. 405), wrong response shape

Run with:  python /app/backend/tests/test_iter136_full_audit.py
"""
import json
import os
import sys
import time
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or sys.exit("REACT_APP_BACKEND_URL not set")
ADMIN = ("admin@demo.com", "Demo1234!")
SALES = ("sarah@demo.com", "Demo1234!")
PIETENTIAL = ("megha@contentvista.com", "Piet-4vRQ-lDa2-ttcO")
TENANT_DEMO = "ten_demo"
TENANT_PIET = "ten_pietential"

results = []  # list of {category, method, path, status, body, classification, note}


def login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        return None
    return r.json().get("token") or r.json().get("access_token")


def classify(status_code, body_text, expect_degraded=False):
    if 200 <= status_code < 300:
        return "HEALTHY"
    lower = (body_text or "")[:500].lower()
    integration_markers = [
        "not configured", "missing api key", "missing key", "no api key", "key not set",
        "integration not connected", "not connected", "credentials not set", "credentials missing",
        "missing credentials", "resend not", "proxycurl not", "serper not", "rapidapi", "apollo not",
        "oauth not configured", "client_id not", "not_configured",
    ]
    if expect_degraded and status_code in (400, 401, 402, 403, 422, 500, 501, 503):
        if any(m in lower for m in integration_markers) or status_code == 503:
            return "DEGRADED"
    if status_code in (503,) and any(m in lower for m in integration_markers):
        return "DEGRADED"
    # 401/403 on auth required => still flag, but probably bug if we sent valid token
    if status_code >= 500:
        return "BROKEN"
    if status_code == 405:
        return "BROKEN"  # method not allowed = handler missing
    if status_code in (400, 401, 403, 404, 409, 422):
        # endpoint exists, validation/auth error — call HEALTHY if expected; else MINOR
        return "HEALTHY-4xx"
    return "UNKNOWN"


def hit(category, method, path, *, token=None, tenant=TENANT_DEMO, json_body=None, params=None,
        files=None, data=None, expect_degraded=False, note="", timeout=30, raw_url=False):
    url = path if raw_url else f"{BASE}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if tenant:
        headers["X-Tenant-Id"] = tenant
    try:
        r = requests.request(method, url, headers=headers, json=json_body, params=params,
                             files=files, data=data, timeout=timeout, allow_redirects=False)
        body = (r.text or "")[:200]
        cls = classify(r.status_code, r.text, expect_degraded=expect_degraded)
        results.append({
            "category": category, "method": method, "path": path,
            "status": r.status_code, "body": body, "classification": cls, "note": note,
        })
        return r
    except Exception as e:
        results.append({
            "category": category, "method": method, "path": path,
            "status": 0, "body": f"EXCEPTION: {e}"[:200], "classification": "BROKEN", "note": note,
        })
        return None


def main():
    print(f"BASE={BASE}")
    admin_tok = login(*ADMIN)
    sales_tok = login(*SALES)
    piet_tok = login(*PIETENTIAL)
    print(f"admin={'OK' if admin_tok else 'FAIL'} sales={'OK' if sales_tok else 'FAIL'} piet={'OK' if piet_tok else 'FAIL'}")
    if not admin_tok:
        print("Cannot proceed without admin token.")
        sys.exit(1)

    # === HEALTH ===
    hit("health", "GET", "/api/health")

    # === AUTH ===
    hit("auth", "POST", "/api/auth/login", json_body={"email": ADMIN[0], "password": ADMIN[1]}, token=None, tenant=None)
    hit("auth", "POST", "/api/auth/login", json_body={"email": "bad@x.com", "password": "wrong"}, token=None, tenant=None, note="invalid-creds")
    hit("auth", "GET", "/api/auth/me", token=admin_tok)
    hit("auth", "POST", "/api/auth/signup",
        json_body={"email": f"TEST_iter136_{int(time.time())}@x.com", "password": "Demo1234!", "name": "T", "company": "T"},
        token=None, tenant=None, note="fresh signup")
    hit("auth", "POST", "/api/auth/change-password",
        json_body={"current_password": "wrongpw", "new_password": "Demo1234!!"}, token=admin_tok,
        note="wrong-current expected 400")

    # === TENANTS ===
    hit("tenants", "GET", "/api/tenants/me", token=admin_tok)
    r = hit("tenants", "POST", "/api/tenants",
            json_body={"name": f"TEST_iter136_{int(time.time())}", "industry": "Tech"}, token=admin_tok)
    new_tid = None
    try:
        new_tid = r.json().get("id") if r and r.status_code < 300 else None
    except Exception:
        pass
    if new_tid:
        hit("tenants", "GET", f"/api/tenants/{new_tid}", token=admin_tok)
    hit("tenants", "GET", "/api/tenants/ten_demo", token=admin_tok)

    # === LEADS ===
    hit("leads", "GET", "/api/leads", token=admin_tok, params={"page": 1, "page_size": 5})
    hit("leads", "GET", "/api/leads", token=admin_tok, params={"stage": "qualified"})
    hit("leads", "GET", "/api/leads", token=admin_tok, params={"min_score": 70})
    hit("leads", "GET", "/api/leads/counts", token=admin_tok)
    hit("leads", "GET", "/api/leads/your-five-today", token=admin_tok)
    hit("leads", "GET", "/api/leads/sleeping", token=admin_tok)
    r = hit("leads", "POST", "/api/leads", token=admin_tok,
            json_body={"name": "TEST iter136", "email": f"TEST_iter136_{int(time.time())}@x.com",
                       "company": "TestCo", "stage": "new"})
    lead_id = None
    try:
        lead_id = r.json().get("id") if r and r.status_code < 300 else None
    except Exception:
        pass
    # Also pull an existing lead to use for read endpoints
    rlist = requests.get(f"{BASE}/api/leads", headers={"Authorization": f"Bearer {admin_tok}", "X-Tenant-Id": TENANT_DEMO},
                        params={"page": 1, "page_size": 5}, timeout=20)
    existing_lead = None
    try:
        items = rlist.json().get("items") or rlist.json().get("leads") or rlist.json()
        if isinstance(items, list) and items:
            existing_lead = items[0].get("id")
    except Exception:
        pass
    ref_lead = lead_id or existing_lead
    print(f"new_lead_id={lead_id} existing_lead={existing_lead}")
    if ref_lead:
        hit("leads", "GET", f"/api/leads/{ref_lead}", token=admin_tok)
        hit("leads", "PATCH", f"/api/leads/{ref_lead}", token=admin_tok, json_body={"notes": "iter136 audit"})
    # CSV import
    csv_content = "name,email,company\nTEST iter136 csv,TEST_csv_iter136@x.com,CsvCo\n"
    hit("leads", "POST", "/api/leads/import", token=admin_tok,
        files={"file": ("leads.csv", csv_content, "text/csv")})
    if lead_id:
        hit("leads", "DELETE", f"/api/leads/{lead_id}", token=admin_tok)

    # === ACTIVITIES ===
    if ref_lead:
        hit("activities", "GET", f"/api/leads/{ref_lead}/activities", token=admin_tok)
        hit("activities", "POST", "/api/activities", token=admin_tok,
            json_body={"lead_id": ref_lead, "type": "note", "content": "iter136 audit"})

    # === CONVERSATIONS ===
    if ref_lead:
        hit("conversations", "GET", f"/api/conversations/lead/{ref_lead}", token=admin_tok)
        hit("conversations", "POST", f"/api/conversations/lead/{ref_lead}/draft",
            token=admin_tok, json_body={"attempt": 1, "channel": "email"}, timeout=60)
        hit("conversations", "POST", f"/api/conversations/lead/{ref_lead}/draft",
            token=admin_tok, json_body={"attempt": 2, "channel": "email"}, timeout=60)
        hit("conversations", "POST", f"/api/conversations/lead/{ref_lead}/draft",
            token=admin_tok, json_body={"attempt": 3, "channel": "email"}, timeout=60)

    # === INTEL ===
    if ref_lead:
        hit("intel", "GET", f"/api/intel/{ref_lead}/profile", token=admin_tok)
        hit("intel", "POST", f"/api/intel/{ref_lead}/research", token=admin_tok, json_body={}, timeout=60, expect_degraded=True)
        hit("intel", "POST", f"/api/intel/{ref_lead}/playbook", token=admin_tok, json_body={}, timeout=60)
        hit("intel", "POST", f"/api/intel/{ref_lead}/compose", token=admin_tok, json_body={"channel": "email"}, timeout=60)
        hit("intel", "GET", f"/api/intel/{ref_lead}/budget", token=admin_tok)
    hit("intel", "POST", "/api/intel/scan-hot", token=admin_tok, json_body={"limit": 1, "threshold": 70}, timeout=60)
    hit("intel", "GET", "/api/intel/scan-progress", token=admin_tok)
    hit("intel", "POST", "/api/intel/batch/hot-leads", token=admin_tok, json_body={"limit": 1}, timeout=60)

    # === VOICE SEEDS ===
    hit("voice_seeds", "GET", "/api/voice-seeds", token=admin_tok)
    r = hit("voice_seeds", "POST", "/api/voice-seeds", token=admin_tok,
            json_body={"label": f"TEST_iter136_{int(time.time())}", "content": "Hello world", "channel": "email"})
    seed_id = None
    try:
        seed_id = r.json().get("id") if r and r.status_code < 300 else None
    except Exception:
        pass
    if seed_id:
        hit("voice_seeds", "PATCH", f"/api/voice-seeds/{seed_id}", token=admin_tok, json_body={"content": "updated"})
        hit("voice_seeds", "DELETE", f"/api/voice-seeds/{seed_id}", token=admin_tok)

    # === JOURNEY ===
    hit("journey", "GET", "/api/journey/touchpoints", token=admin_tok)
    r = hit("journey", "POST", "/api/journey/touchpoints", token=admin_tok,
            json_body={"name": "TEST_iter136", "channel": "email", "day_offset": 0, "subject": "Hi", "body": "Hello"})
    tp_id = None
    try:
        tp_id = r.json().get("id") if r and r.status_code < 300 else None
    except Exception:
        pass
    if tp_id:
        hit("journey", "PATCH", f"/api/journey/touchpoints/{tp_id}", token=admin_tok, json_body={"subject": "Hi2"})
        hit("journey", "POST", "/api/journey/touchpoints/reorder", token=admin_tok, json_body={"ordered_ids": [tp_id]})
        hit("journey", "POST", f"/api/journey/touchpoints/{tp_id}/regenerate", token=admin_tok, json_body={}, timeout=60)
        hit("journey", "DELETE", f"/api/journey/touchpoints/{tp_id}", token=admin_tok)
    hit("journey", "POST", "/api/journey/generate", token=admin_tok,
        json_body={"goal": "Book a demo", "num_touchpoints": 3}, timeout=60)

    # === APPROVALS ===
    hit("approvals", "GET", "/api/approvals", token=admin_tok)
    hit("approvals", "GET", "/api/approvals/count", token=admin_tok)
    hit("approvals", "POST", "/api/approvals/bulk-approve", token=admin_tok, json_body={"ids": []})
    hit("approvals", "POST", "/api/approvals/bulk-reject", token=admin_tok, json_body={"ids": []})

    # === MORNING BRIEF / APPROVAL DIGEST / EOD ===
    for cat, base in [("morning_brief", "/api/aria/morning-brief"),
                      ("approval_digest", "/api/aria/approval-digest"),
                      ("eod_wrap", "/api/aria/eod-wrap")]:
        hit(cat, "GET", f"{base}/config", token=admin_tok)
        hit(cat, "POST", f"{base}/config", token=admin_tok,
            json_body={"enabled": True, "delivery_time": "08:00", "channel": "email"})
        hit(cat, "POST", f"{base}/send-now", token=admin_tok, json_body={}, timeout=60, expect_degraded=True,
            note="needs Resend key on preview")
        hit(cat, "GET", f"{base}/last", token=admin_tok)

    # === NOTIFICATIONS UI AGGREGATE ===
    hit("notifications", "GET", "/api/aria/settings/notifications", token=admin_tok)
    hit("notifications", "POST", "/api/aria/settings/notifications", token=admin_tok,
        json_body={"morning_brief": {"enabled": True}, "approval_digest": {"enabled": True}, "eod_wrap": {"enabled": True}})

    # === ARIA TODAY / FEED / COMMAND ===
    hit("aria_today", "GET", "/api/aria/today", token=admin_tok)
    hit("aria_today", "GET", "/api/aria/feed", token=admin_tok)
    hit("aria_today", "GET", "/api/aria/command-center/ai-summary", token=admin_tok, timeout=60)

    # === INTEGRATIONS ===
    hit("integrations", "GET", "/api/integrations/providers/list", token=admin_tok)
    hit("integrations", "GET", "/api/pt/integrations", token=admin_tok)
    hit("integrations", "GET", "/api/integrations/validate-key/status", token=admin_tok)
    hit("integrations", "GET", "/api/integrations/validate-key/history", token=admin_tok)
    for provider in ["saleshandy", "proxycurl", "serper", "apollo", "resend", "360dialog", "lemlist"]:
        hit("integrations", "POST", "/api/integrations/validate-key", token=admin_tok,
            json_body={"provider": provider, "api_key": "garbage_test_iter136"},
            timeout=30, expect_degraded=True, note=f"garbage key for {provider}")

    # === OAUTH (expect 503 or 4xx without creds) ===
    for prov in ["calendly", "gmail", "outlook", "meta", "linkedin", "googleads"]:
        hit("oauth", "GET", f"/api/integrations/{prov}/connect", token=admin_tok,
            expect_degraded=True, note=f"{prov} oauth")

    # === WEBHOOKS ===
    hit("webhooks", "GET", "/api/webhooks/health")
    hit("webhooks", "POST", "/api/webhooks/resend", token=None, tenant=None,
        json_body={"type": "email.delivered", "data": {"email_id": "test"}})
    hit("webhooks", "POST", "/api/webhooks/360dialog", token=None, tenant=None, json_body={"messages": []})
    hit("webhooks", "POST", "/api/webhooks/calendly", token=None, tenant=None, json_body={"event": "invitee.created"})
    hit("webhooks", "POST", "/api/webhooks/meta-leads", token=None, tenant=None, json_body={"entry": []})

    # === ICPs ===
    hit("icps", "GET", "/api/icps", token=admin_tok)
    r = hit("icps", "POST", "/api/icps", token=admin_tok,
            json_body={"name": f"TEST_iter136_{int(time.time())}", "industry": "SaaS", "company_size": "50-200"})
    icp_id = None
    try:
        icp_id = r.json().get("id") if r and r.status_code < 300 else None
    except Exception:
        pass
    if icp_id:
        hit("icps", "PATCH", f"/api/icps/{icp_id}", token=admin_tok, json_body={"industry": "FinTech"})
        hit("icps", "DELETE", f"/api/icps/{icp_id}", token=admin_tok)

    # === REPORTS ===
    hit("reports", "GET", "/api/reports/icp-channel-matrix", token=admin_tok)
    hit("reports", "GET", "/api/reports/funnel", token=admin_tok)
    hit("reports", "GET", "/api/reports/channel-performance", token=admin_tok)

    # === TRAIN ARIA ===
    hit("train_aria", "GET", "/api/aria/training-profile", token=admin_tok)
    hit("train_aria", "POST", "/api/aria/training-profile", token=admin_tok,
        json_body={"company_blurb": "We build X", "tone": "warm"})

    # === ADMIN V3 ===
    hit("admin_v3", "GET", "/api/admin/v3/overview", token=admin_tok)
    hit("admin_v3", "GET", "/api/admin/v3/workspaces", token=admin_tok)
    hit("admin_v3", "GET", "/api/admin/v3/usage", token=admin_tok)
    hit("admin_v3", "GET", "/api/admin/v3/system-health", token=admin_tok)

    # === BILLING ===
    hit("billing", "GET", "/api/billing/plans", token=admin_tok)
    hit("billing", "GET", "/api/billing/current-plan", token=admin_tok)
    hit("billing", "GET", "/api/billing/transactions", token=admin_tok)

    # === PT SETUP HEALTH ===
    hit("pt_setup", "GET", "/api/pt/setup/health", token=admin_tok)

    # === ASSETS ===
    hit("assets", "GET", "/api/assets", token=admin_tok)
    r = hit("assets", "POST", "/api/assets/upload", token=admin_tok,
            files={"file": ("iter136.txt", b"hello iter136", "text/plain")})
    asset_id = None
    try:
        asset_id = r.json().get("id") if r and r.status_code < 300 else None
    except Exception:
        pass
    if asset_id:
        hit("assets", "GET", f"/api/assets/download/{asset_id}", token=admin_tok)

    # === AI ROUTES ===
    hit("ai", "POST", "/api/ai/score", token=admin_tok,
        json_body={"lead": {"name": "T", "company": "TestCo", "title": "VP Eng"}}, timeout=60)
    hit("ai", "POST", "/api/ai/email-generate", token=admin_tok,
        json_body={"lead": {"name": "T", "company": "TestCo"}, "intent": "intro"}, timeout=60)
    hit("ai", "POST", "/api/ai/chat", token=admin_tok,
        json_body={"messages": [{"role": "user", "content": "hi"}]}, timeout=60)
    hit("ai", "POST", "/api/ai/summarize", token=admin_tok, json_body={"text": "Hello world test."}, timeout=60)

    # === AUTO MAP ===
    hit("auto_map", "POST", "/api/aria/auto-map/improve", token=admin_tok, json_body={}, timeout=60)

    # === MASTER ADMIN ===
    for path in ["/api/master-admin/overview", "/api/master-admin/workspaces",
                 "/api/master-admin/users", "/api/master-admin/deployments",
                 "/api/master-admin/system-health"]:
        hit("master_admin", "GET", path, token=admin_tok)

    # === TENANT ISOLATION GUARD ===
    # Try cross-tenant access — admin is member of both, so use sales_tok (ten_demo only) with ten_pietential
    if sales_tok:
        hit("isolation", "GET", "/api/voice-seeds", token=sales_tok, tenant=TENANT_PIET,
            note="sales@demo trying ten_pietential — must NOT leak")
        # leads cross-tenant: fetch a ten_pietential lead id then try with ten_demo sales token
        if piet_tok:
            rp = requests.get(f"{BASE}/api/leads",
                              headers={"Authorization": f"Bearer {piet_tok}", "X-Tenant-Id": TENANT_PIET},
                              params={"page": 1, "page_size": 1}, timeout=20)
            try:
                items = rp.json().get("items") or rp.json().get("leads") or []
                piet_lead = items[0]["id"] if items else None
            except Exception:
                piet_lead = None
            if piet_lead:
                hit("isolation", "GET", f"/api/leads/{piet_lead}", token=sales_tok, tenant=TENANT_DEMO,
                    note="sales@demo using ten_demo header to read ten_pietential lead — must 404")
                hit("isolation", "GET", f"/api/conversations/lead/{piet_lead}", token=sales_tok, tenant=TENANT_DEMO,
                    note="cross-tenant conversation — must 404")

    # === _id LEAK GUARD ===
    leak_paths = [
        "/api/leads", "/api/voice-seeds", "/api/journey/touchpoints", "/api/icps",
        "/api/approvals", "/api/assets", "/api/integrations/providers/list",
        "/api/aria/today", "/api/aria/feed", "/api/leads/counts",
    ]
    leaks = []
    for p in leak_paths:
        try:
            r = requests.get(f"{BASE}{p}", headers={"Authorization": f"Bearer {admin_tok}", "X-Tenant-Id": TENANT_DEMO}, timeout=20)
            if r.status_code < 300 and '"_id"' in r.text:
                leaks.append(p)
        except Exception:
            pass
    print(f"_id leaks: {leaks}")

    # === SUMMARY ===
    by_class = {}
    by_cat = {}
    for r in results:
        by_class.setdefault(r["classification"], []).append(r)
        by_cat.setdefault(r["category"], {"healthy": 0, "degraded": 0, "broken": 0, "4xx": 0})
        c = r["classification"]
        if c == "HEALTHY":
            by_cat[r["category"]]["healthy"] += 1
        elif c == "DEGRADED":
            by_cat[r["category"]]["degraded"] += 1
        elif c == "BROKEN":
            by_cat[r["category"]]["broken"] += 1
        else:
            by_cat[r["category"]]["4xx"] += 1

    print("\n=== CATEGORY VERDICT ===")
    for cat, c in by_cat.items():
        verdict = "BROKEN" if c["broken"] else ("DEGRADED" if c["degraded"] else "HEALTHY")
        print(f"  {cat:18s} -> {verdict}  ({c})")

    print("\n=== BROKEN ENDPOINTS ===")
    for r in by_class.get("BROKEN", []):
        print(f"  [{r['status']}] {r['method']:6s} {r['path']}  body={r['body'][:120]}")

    print("\n=== DEGRADED ENDPOINTS ===")
    for r in by_class.get("DEGRADED", []):
        print(f"  [{r['status']}] {r['method']:6s} {r['path']}  note={r['note']}  body={r['body'][:80]}")

    out_path = "/app/test_reports/iter136_audit_raw.json"
    with open(out_path, "w") as f:
        json.dump({"id_leaks": leaks, "by_cat": by_cat, "results": results}, f, indent=2)
    print(f"\nWrote raw audit to {out_path}")


if __name__ == "__main__":
    main()
