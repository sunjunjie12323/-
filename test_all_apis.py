#!/usr/bin/env python3
import json
import sys
import urllib.request
import urllib.error
from urllib.parse import quote

BASE = "http://localhost:8001/api/v1"
TOKEN = None
RESULTS = {"pass": [], "fail": []}

def req(method, path, data=None, headers=None, expect_status=None, expect_2xx=False):
    url = f"{BASE}{path}"
    hdrs = {"Content-Type": "application/json"}
    if TOKEN:
        hdrs["Authorization"] = f"Bearer {TOKEN}"
    if headers:
        hdrs.update(headers)
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=15)
        status = resp.status
        try:
            rdata = json.loads(resp.read().decode())
        except:
            rdata = {}
        if expect_status is not None:
            ok = status == expect_status
        elif expect_2xx:
            ok = 200 <= status < 300
        else:
            ok = status == 200
        return {"status": status, "data": rdata, "ok": ok}
    except urllib.error.HTTPError as e:
        try:
            rdata = json.loads(e.read().decode())
        except:
            rdata = {}
        if expect_status is not None:
            ok = e.code == expect_status
        elif expect_2xx:
            ok = 200 <= e.code < 300
        else:
            ok = e.code == 200
        return {"status": e.code, "data": rdata, "ok": ok}
    except Exception as e:
        return {"status": 0, "data": {"error": str(e)}, "ok": False}

def test(name, result):
    if result["ok"]:
        RESULTS["pass"].append(f"[PASS] {name} (HTTP {result['status']})")
        print(f"  ✅ {name} — HTTP {result['status']}")
    else:
        RESULTS["fail"].append(f"[FAIL] {name} (HTTP {result['status']}) — {json.dumps(result['data'], ensure_ascii=False)[:200]}")
        print(f"  ❌ {name} — HTTP {result['status']} — {json.dumps(result['data'], ensure_ascii=False)[:200]}")

def safe_list(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return list(obj.values())
    return []

def safe_get(obj, key, default="MISSING"):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

print("=" * 60)
print("1. AUTH API TESTS")
print("=" * 60)

r = req("POST", "/auth/login", {"username": "admin", "password": "admin123"}, expect_status=200)
test("Login admin", r)
if r["ok"]:
    TOKEN = r["data"].get("access_token")
    user = r["data"].get("user", {})
    print(f"  User: {safe_get(user,'username')} / {safe_get(user,'role')}")
else:
    print("  🛑 LOGIN FAILED")
    sys.exit(1)

r = req("GET", "/auth/me", expect_status=200)
test("Get current user", r)

r = req("POST", "/auth/login", {"username": "admin", "password": "wrong"}, expect_status=401)
test("Login wrong password (401)", r)

r = req("POST", "/auth/register", {"username": "e2e_test_user2", "password": "test123456", "role": "analyst"}, expect_2xx=True)
test("Register new user", r)

r = req("GET", "/auth/users", expect_status=200)
test("List users", r)

print("\n" + "=" * 60)
print("2. DASHBOARD API TESTS")
print("=" * 60)

r = req("GET", "/dashboard/stats", expect_status=200)
test("Dashboard stats", r)
if r["ok"]:
    d = r["data"]
    for k in ["total_intelligence", "active_pirs", "threat_level_distribution"]:
        print(f"  {k}: {safe_get(d, k)}")

r = req("GET", "/dashboard/recent?limit=5", expect_status=200)
test("Dashboard recent", r)

r = req("GET", "/dashboard/threat-distribution", expect_status=200)
test("Threat distribution", r)

r = req("GET", "/dashboard/agent-status", expect_status=200)
test("Agent status", r)

print("\n" + "=" * 60)
print("3. INTELLIGENCE API TESTS")
print("=" * 60)

r = req("GET", "/intelligence", expect_status=200)
test("List intelligence", r)
if r["ok"]:
    print(f"  Total: {safe_get(r['data'],'total')}, Items: {len(safe_list(safe_get(r['data'],'items',[])))}")

r = req("GET", "/intelligence?limit=5&offset=0", expect_status=200)
test("Intelligence pagination", r)

r = req("GET", f"/intelligence?search={quote('诈骗')}", expect_status=200)
test("Search intelligence (Chinese)", r)

r = req("GET", "/intelligence?source=telegram", expect_status=200)
test("Filter by source", r)

r = req("GET", "/intelligence?threat_level=critical", expect_status=200)
test("Filter by threat_level", r)

r = req("GET", "/intelligence/stats", expect_status=200)
test("Intelligence stats", r)

r = req("POST", "/intelligence", {"source": "forum", "content": "E2E测试情报内容", "source_url": "https://test.example.com"}, expect_2xx=True)
test("Create intelligence", r)
new_intel_id = safe_get(r["data"], "id") if r["ok"] else None
print(f"  New ID: {new_intel_id}")

if new_intel_id:
    r = req("GET", f"/intelligence/{new_intel_id}", expect_status=200)
    test("Get intelligence by ID", r)
    r = req("PATCH", f"/intelligence/{new_intel_id}/status", {"status": "analyzed"}, expect_2xx=True)
    test("Update status", r)
    r = req("DELETE", f"/intelligence/{new_intel_id}", expect_2xx=True)
    test("Delete intelligence", r)

r = req("GET", "/intelligence/nonexistent-id-xxx", expect_status=404)
test("Get nonexistent (404)", r)

print("\n" + "=" * 60)
print("4. BLACKTALK API TESTS")
print("=" * 60)

r = req("GET", "/blacktalk/terms", expect_status=200)
test("List terms", r)
if r["ok"]:
    print(f"  Total: {safe_get(r['data'],'total')}")

r = req("GET", "/blacktalk/terms?category=fraud", expect_status=200)
test("Filter by category", r)

r = req("GET", f"/blacktalk/terms?search={quote('跑分')}", expect_status=200)
test("Search terms (Chinese)", r)

r = req("POST", "/blacktalk/decode", {"text": "他在跑分，用猫池洗白"}, expect_status=200)
test("Decode blacktalk", r)
if r["ok"]:
    d = r["data"]
    decoded = safe_get(d, "decoded_terms", [])
    if isinstance(decoded, dict):
        decoded = list(decoded.values())
    print(f"  Decoded count: {len(decoded) if isinstance(decoded, list) else 'N/A'}")

r = req("GET", f"/blacktalk/search?q={quote('跑分')}&n=5", expect_status=200)
test("Search blacktalk GET", r)

r = req("GET", "/blacktalk/stats", expect_status=200)
test("Blacktalk stats", r)
if r["ok"]:
    print(f"  Stats: {json.dumps(r['data'], ensure_ascii=False)[:200]}")

r = req("POST", "/blacktalk/terms", {"term": "测试黑话E2E", "meaning": "测试含义", "category": "general", "source": "manual"}, expect_2xx=True)
test("Add term", r)

print("\n" + "=" * 60)
print("5. GRAPH API TESTS")
print("=" * 60)

r = req("GET", "/graph/stats", expect_status=200)
test("Graph stats", r)
if r["ok"]:
    print(f"  Nodes: {safe_get(r['data'],'node_count')}, Edges: {safe_get(r['data'],'edge_count')}")

r = req("GET", "/graph/data", expect_status=200)
test("Get graph data", r)
if r["ok"]:
    d = r["data"]
    nodes = safe_list(safe_get(d, "nodes", []))
    edges = safe_list(safe_get(d, "edges", []))
    print(f"  Nodes: {len(nodes)}, Edges: {len(edges)}")

r = req("GET", "/graph/entities", expect_status=200)
test("List entities", r)

r = req("POST", "/graph/entities", {"type": "phone", "value": "13900139000", "context": "e2e test"}, expect_2xx=True)
test("Add entity", r)
new_entity_id = safe_get(r["data"], "id") if r["ok"] else None

if new_entity_id:
    r = req("GET", f"/graph/entities/{new_entity_id}", expect_status=200)
    test("Get entity by ID", r)

r = req("GET", "/graph/relations", expect_status=200)
test("List relations", r)

r = req("POST", "/graph/communities", {"algorithm": "louvain", "min_size": 2}, expect_status=200)
test("Find communities", r)

r = req("GET", "/graph/export", expect_status=200)
test("Export graph", r)

print("\n" + "=" * 60)
print("6. PIR API TESTS")
print("=" * 60)

r = req("GET", "/pirs", expect_status=200)
test("List PIRs", r)
if r["ok"]:
    print(f"  Total: {safe_get(r['data'],'total')}")

r = req("POST", "/pirs", {"title": "E2E测试PIR", "description": "自动化测试", "priority": "high", "keywords": ["测试"]}, expect_2xx=True)
test("Create PIR", r)
new_pir_id = safe_get(r["data"], "id") if r["ok"] else None

if new_pir_id:
    r = req("GET", f"/pirs/{new_pir_id}", expect_status=200)
    test("Get PIR by ID", r)
    r = req("PATCH", f"/pirs/{new_pir_id}", {"description": "更新描述"}, expect_2xx=True)
    test("Update PIR", r)
    r = req("DELETE", f"/pirs/{new_pir_id}", expect_2xx=True)
    test("Delete PIR", r)

print("\n" + "=" * 60)
print("7. REPORTS API TESTS")
print("=" * 60)

r = req("GET", "/reports", expect_status=200)
test("List reports", r)

r = req("POST", "/reports/generate", {"title": "E2E测试报告", "report_type": "threat_analysis"}, expect_2xx=True)
test("Generate report", r)
new_report_id = safe_get(r["data"], "id") if r["ok"] else None

if new_report_id:
    r = req("GET", f"/reports/{new_report_id}", expect_status=200)
    test("Get report by ID", r)
    r = req("POST", f"/reports/{new_report_id}/export?format=markdown", None, expect_status=200)
    test("Export report", r)
    r = req("DELETE", f"/reports/{new_report_id}", expect_2xx=True)
    test("Delete report", r)

print("\n" + "=" * 60)
print("8. AGENT API TESTS")
print("=" * 60)

r = req("GET", "/agent/status", expect_status=200)
test("Agent status", r)

r = req("GET", "/agent/history", expect_status=200)
test("Agent history", r)

r = req("POST", "/agent/query", {"query": "最近的诈骗趋势"}, expect_2xx=True)
test("Submit query", r)
task_id = safe_get(r["data"], "task_id") if r["ok"] else None

r = req("POST", "/agent/collect", expect_2xx=True)
test("Trigger collect", r)

print("\n" + "=" * 60)
print("9. TASKS API TESTS")
print("=" * 60)

r = req("GET", "/tasks", expect_status=200)
test("List tasks", r)

if task_id:
    r = req("GET", f"/tasks/{task_id}", expect_status=200)
    test("Get task by ID", r)

print("\n" + "=" * 60)
print("10. UNAUTHENTICATED ACCESS TEST")
print("=" * 60)

saved = TOKEN
TOKEN = None
r = req("GET", "/dashboard/stats", expect_status=401)
test("Unauth access (expect 401)", r)
TOKEN = saved

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  PASSED: {len(RESULTS['pass'])}")
print(f"  FAILED: {len(RESULTS['fail'])}")
if RESULTS["fail"]:
    print("\n  FAILED TESTS:")
    for f in RESULTS["fail"]:
        print(f"    {f}")
print("=" * 60)
sys.exit(len(RESULTS["fail"]))
