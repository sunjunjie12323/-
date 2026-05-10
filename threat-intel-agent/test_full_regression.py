import requests
import json

BASE = "http://localhost:8001/api/v1"

def login():
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
    return r.json()["access_token"]

def headers(token):
    return {"Authorization": f"Bearer {token}"}

def test_regression():
    token = login()
    h = headers(token)
    results = {"pass": 0, "fail": 0, "errors": []}
    
    def check(name, response, expected_status=200):
        if response.status_code == expected_status:
            results["pass"] += 1
            print(f"  ✅ {name}")
            return True
        else:
            results["fail"] += 1
            err = f"  ❌ {name}: Expected {expected_status}, got {response.status_code}: {response.text[:150]}"
            results["errors"].append(err)
            print(err)
            return False

    # === Core APIs ===
    print("\n=== Core APIs ===")
    check("health", requests.get("http://localhost:8001/health"))
    check("dashboard_stats", requests.get(f"{BASE}/dashboard/stats", headers=h))
    check("intelligence_list", requests.get(f"{BASE}/intelligence", headers=h))
    check("blacktalk_terms", requests.get(f"{BASE}/blacktalk/terms", headers=h))
    check("blacktalk_stats", requests.get(f"{BASE}/blacktalk/stats", headers=h))
    check("graph_stats", requests.get(f"{BASE}/graph/stats", headers=h))
    check("entities_list", requests.get(f"{BASE}/entities", headers=h))
    check("pirs_list", requests.get(f"{BASE}/pirs", headers=h))
    check("reports_list", requests.get(f"{BASE}/reports", headers=h))
    check("tasks_list", requests.get(f"{BASE}/tasks", headers=h))
    check("agent_status", requests.get(f"{BASE}/agent/status", headers=h))
    
    # === BlackTalk Decode (DeepSeek) ===
    print("\n=== BlackTalk Decode (DeepSeek LLM) ===")
    r = requests.post(f"{BASE}/blacktalk/decode", headers=h, json={"text": "这个料子很顶，上分快"})
    check("blacktalk_decode", r)
    if r.status_code == 200:
        decoded = r.json()
        terms = decoded.get("decoded_terms", decoded.get("terms", []))
        print(f"    Decoded terms: {len(terms)}")
    
    # === Innovation: Zero-Day ===
    print("\n=== Innovation: Zero-Day ===")
    r = requests.post(f"{BASE}/zero-day/detect", headers=h, json={"text": "这个套路上分很稳，质量很顶"})
    check("zero_day_detect", r)
    
    # === Innovation: Attack Prediction ===
    print("\n=== Innovation: Attack Prediction ===")
    r = requests.post(f"{BASE}/attack-prediction/predict", headers=h, json={"entity_id": "test-entity", "depth": 2})
    check("attack_prediction", r)
    
    # === Innovation: Provenance ===
    print("\n=== Innovation: Provenance ===")
    r = requests.post(f"{BASE}/provenance/record", headers=h, json={
        "intelligence_id": "regression-test-001",
        "source": "test",
        "content": "Test intelligence for regression",
        "operator_type": "collector",
        "confidence": 0.8
    })
    check("provenance_record", r)
    
    # === Innovation: Attribution ===
    print("\n=== Innovation: Attribution ===")
    r = requests.post(f"{BASE}/attribution/fingerprint/test-entity", headers=h)
    check("attribution_fingerprint", r)
    
    # === Innovation: Temporal Decay ===
    print("\n=== Innovation: Temporal Decay ===")
    r = requests.get(f"{BASE}/decay/batch", headers=h)
    check("decay_batch", r)
    r = requests.get(f"{BASE}/decay/recommendations", headers=h)
    check("decay_recommendations", r)
    
    # === Innovation: Organism (Full Lifecycle) ===
    print("\n=== Innovation: Organism (Full Lifecycle) ===")
    
    # Spawn
    r = requests.post(f"{BASE}/organism/spawn", headers=h, json={
        "intelligence_id": "regression-org-campaign",
        "species": "campaign",
        "initial_data": {"value": "campaign-2026-Q2", "threat_type": "fraud_campaign", "confidence": 0.8}
    })
    check("organism_spawn", r)
    
    # Evolve
    r = requests.post(f"{BASE}/organism/evolve", headers=h, json={
        "organism_id": "regression-org-campaign",
        "new_data": {"confidence": 0.9, "confirmed": True, "new_target": "bank-001"},
        "trigger": "new_evidence"
    })
    check("organism_evolve", r)
    
    # Vitality
    r = requests.get(f"{BASE}/organism/vitality/regression-org-campaign", headers=h)
    check("organism_vitality", r)
    
    # Timeline
    r = requests.get(f"{BASE}/organism/timeline/regression-org-campaign", headers=h)
    check("organism_timeline", r)
    
    # Genealogy
    r = requests.get(f"{BASE}/organism/genealogy/regression-org-campaign", headers=h)
    check("organism_genealogy", r)
    
    # Register prediction
    r = requests.post(f"{BASE}/organism/prediction/register", headers=h, json={
        "entity_id": "regression-org-campaign",
        "predicted_steps": [
            {"action": "expand_targets", "probability": 0.6},
            {"action": "launder_money", "probability": 0.4}
        ],
        "validation_window_hours": 72
    })
    check("organism_register_prediction", r)
    
    # Validate predictions
    r = requests.post(f"{BASE}/organism/prediction/validate", headers=h)
    check("organism_validate_predictions", r)
    
    # Accuracy
    r = requests.get(f"{BASE}/organism/prediction/accuracy", headers=h)
    check("organism_accuracy", r)
    
    # Calibrate
    r = requests.post(f"{BASE}/organism/prediction/calibrate", headers=h)
    check("organism_calibrate", r)
    
    # Archive
    r = requests.post(f"{BASE}/organism/gene/archive/regression-org-campaign?cause=test_complete", headers=h)
    check("organism_archive", r)
    
    # Gene matches
    r = requests.post(f"{BASE}/organism/gene/match", headers=h, json={
        "new_intelligence_data": {"species": "campaign", "value": "new-campaign"}
    })
    check("organism_gene_match", r)
    
    # List organisms
    r = requests.get(f"{BASE}/organism/organisms?alive_only=false", headers=h)
    check("organism_list", r)
    
    # List genes
    r = requests.get(f"{BASE}/organism/genes", headers=h)
    check("organism_genes", r)
    
    # Lifecycle check
    r = requests.post(f"{BASE}/organism/lifecycle-check", headers=h)
    check("organism_lifecycle", r)
    
    # === Auth Tests ===
    print("\n=== Auth Tests ===")
    r = requests.get(f"{BASE}/intelligence")
    check("unauth_blocked", r, 401)
    
    # === Agent Query (Task Queue) ===
    print("\n=== Agent Query (Task Queue) ===")
    r = requests.post(f"{BASE}/agent/query", headers=h, json={"query": "测试查询"})
    check("agent_query_submit", r)
    if r.status_code == 200:
        task_id = r.json().get("task_id")
        if task_id:
            r2 = requests.get(f"{BASE}/agent/task/{task_id}", headers=h)
            check("agent_task_status", r2)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"REGRESSION TEST: {results['pass']} passed, {results['fail']} failed")
    if results['errors']:
        print("\nErrors:")
        for e in results['errors']:
            print(e)
    return results

if __name__ == "__main__":
    test_regression()
