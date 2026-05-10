import requests
import json
import time

BASE = "http://localhost:8001/api/v1"

def login():
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]

def headers(token):
    return {"Authorization": f"Bearer {token}"}

def test_organism_apis():
    token = login()
    h = headers(token)
    results = {"pass": 0, "fail": 0, "errors": []}
    
    def check(name, response, expected_status=200):
        if response.status_code == expected_status:
            results["pass"] += 1
            print(f"  ✅ {name} - {response.status_code}")
            return True
        else:
            results["fail"] += 1
            err = f"  ❌ {name} - Expected {expected_status}, got {response.status_code}: {response.text[:200]}"
            results["errors"].append(err)
            print(err)
            return False

    # 1. Health check - verify organism engine is loaded
    print("\n=== Test 1: Health Check ===")
    r = requests.get("http://localhost:8001/health")
    check("health_check", r)
    data = r.json()
    organism_loaded = data.get("services", {}).get("intelligence_organism", False)
    if organism_loaded:
        print("  ✅ IntelligenceOrganismEngine loaded")
        results["pass"] += 1
    else:
        print("  ❌ IntelligenceOrganismEngine NOT loaded")
        results["fail"] += 1
        results["errors"].append("IntelligenceOrganismEngine not in health check")

    # 2. Spawn organism - IP type
    print("\n=== Test 2: Spawn Organism (IP) ===")
    r = requests.post(f"{BASE}/organism/spawn", headers=h, json={
        "intelligence_id": "org-ip-192.168.1.1",
        "species": "ip",
        "initial_data": {
            "value": "192.168.1.1",
            "threat_type": "c2_server",
            "confidence": 0.85,
            "related_entities": ["org-phone-13800138000"],
            "source": "darkweb_monitor"
        }
    })
    check("spawn_ip_organism", r)
    ip_org = r.json() if r.status_code == 200 else {}
    print(f"  Species: {ip_org.get('species')}, Generation: {ip_org.get('generation')}, Vitality: {ip_org.get('vitality')}")

    # 3. Spawn organism - Phone type
    print("\n=== Test 3: Spawn Organism (Phone) ===")
    r = requests.post(f"{BASE}/organism/spawn", headers=h, json={
        "intelligence_id": "org-phone-13800138000",
        "species": "phone",
        "initial_data": {
            "value": "13800138000",
            "threat_type": "fraud_phone",
            "confidence": 0.7,
            "related_entities": ["org-ip-192.168.1.1"],
            "source": "telegram_monitor"
        }
    })
    check("spawn_phone_organism", r)
    phone_org = r.json() if r.status_code == 200 else {}

    # 4. Spawn organism - Slang type
    print("\n=== Test 4: Spawn Organism (Slang) ===")
    r = requests.post(f"{BASE}/organism/spawn", headers=h, json={
        "intelligence_id": "org-slang-shangfen",
        "species": "slang",
        "initial_data": {
            "value": "上分",
            "threat_type": "gambling_term",
            "confidence": 0.9,
            "source": "forum_monitor"
        }
    })
    check("spawn_slang_organism", r)

    # 5. Spawn organism - TTP type
    print("\n=== Test 5: Spawn Organism (TTP) ===")
    r = requests.post(f"{BASE}/organism/spawn", headers=h, json={
        "intelligence_id": "org-ttp-phishing",
        "species": "ttp",
        "initial_data": {
            "value": "phishing_kit_v3",
            "threat_type": "phishing",
            "confidence": 0.6,
            "attack_chain": ["recon", "weaponize", "phish", "credential_harvest"],
            "ttp": "T1566"
        }
    })
    check("spawn_ttp_organism", r)

    # 6. Check vitality
    print("\n=== Test 6: Check Vitality ===")
    r = requests.get(f"{BASE}/organism/vitality/org-ip-192.168.1.1", headers=h)
    check("check_vitality_ip", r)
    if r.status_code == 200:
        v = r.json()
        print(f"  Vitality: {v.get('vitality')}, Freshness: {v.get('freshness')}, Activity: {v.get('activity')}, Relevance: {v.get('relevance')}")
        print(f"  Is alive: {v.get('is_alive')}, Recommended: {v.get('recommended_action')}")

    # 7. Evolve organism
    print("\n=== Test 7: Evolve Organism ===")
    r = requests.post(f"{BASE}/organism/evolve", headers=h, json={
        "organism_id": "org-ip-192.168.1.1",
        "new_data": {
            "confidence": 0.95,
            "confirmed": True,
            "new_association": "org-bankcard-622848",
            "context": "C2 server actively communicating with malware"
        },
        "trigger": "new_evidence"
    })
    check("evolve_organism", r)
    if r.status_code == 200:
        evolved = r.json()
        print(f"  Vitality after evolution: {evolved.get('vitality')}")
        print(f"  Mutations: {len(evolved.get('mutations', []))}")
        print(f"  Evolution log entries: {len(evolved.get('evolution_log', []))}")

    # 8. Get timeline
    print("\n=== Test 8: Get Evolution Timeline ===")
    r = requests.get(f"{BASE}/organism/timeline/org-ip-192.168.1.1", headers=h)
    check("get_timeline", r)
    if r.status_code == 200:
        events = r.json().get("events", [])
        print(f"  Timeline events: {len(events)}")
        for ev in events[:3]:
            print(f"    [{ev.get('event_type')}] {ev.get('description', '')[:80]}")

    # 9. Find offspring
    print("\n=== Test 9: Find Offspring ===")
    r = requests.get(f"{BASE}/organism/offspring/org-ip-192.168.1.1?depth=2", headers=h)
    check("find_offspring", r)
    if r.status_code == 200:
        tree = r.json()
        print(f"  Nodes: {len(tree.get('nodes', []))}, Edges: {len(tree.get('edges', []))}")

    # 10. Register prediction
    print("\n=== Test 10: Register Prediction ===")
    r = requests.post(f"{BASE}/organism/prediction/register", headers=h, json={
        "entity_id": "org-ip-192.168.1.1",
        "predicted_steps": [
            {"action": "domain_registration", "probability": 0.7, "description": "Will register new C2 domain"},
            {"action": "phishing_campaign", "probability": 0.5, "description": "Will launch phishing campaign"},
            {"action": "lateral_movement", "probability": 0.3, "description": "Will attempt lateral movement"}
        ],
        "validation_window_hours": 168
    })
    check("register_prediction", r)
    if r.status_code == 200:
        pred = r.json()
        print(f"  Prediction ID: {pred.get('prediction_id')}")
        print(f"  Steps: {len(pred.get('predicted_steps', []))}")
        print(f"  Deadline: {pred.get('validation_deadline')}")

    # 11. Validate predictions
    print("\n=== Test 11: Validate Predictions ===")
    r = requests.post(f"{BASE}/organism/prediction/validate", headers=h)
    check("validate_predictions", r)
    if r.status_code == 200:
        val_data = r.json()
        validations = val_data.get("validations", [])
        print(f"  Validations: {len(validations)}")

    # 12. Get prediction accuracy
    print("\n=== Test 12: Get Prediction Accuracy ===")
    r = requests.get(f"{BASE}/organism/prediction/accuracy", headers=h)
    check("get_prediction_accuracy", r)
    if r.status_code == 200:
        acc = r.json()
        print(f"  Total predictions: {acc.get('total_predictions')}")
        print(f"  Accuracy: {acc.get('accuracy')}")
        print(f"  Brier score: {acc.get('brier_score')}")

    # 13. Calibrate model
    print("\n=== Test 13: Calibrate Model ===")
    r = requests.post(f"{BASE}/organism/prediction/calibrate", headers=h)
    check("calibrate_model", r)
    if r.status_code == 200:
        cal = r.json()
        print(f"  Bias direction: {cal.get('bias_direction')}")
        print(f"  Sample size: {cal.get('sample_size')}")

    # 14. Archive organism and preserve genes
    print("\n=== Test 14: Archive Organism (Gene Preservation) ===")
    r = requests.post(f"{BASE}/organism/gene/archive/org-phone-13800138000?cause=expired", headers=h)
    check("archive_organism", r)
    if r.status_code == 200:
        gene = r.json()
        print(f"  Gene ID: {gene.get('gene_id')}")
        print(f"  Species: {gene.get('species')}")
        print(f"  Patterns: {gene.get('patterns')}")
        print(f"  Associations: {gene.get('associations')}")
        print(f"  Attack chains: {gene.get('attack_chains')}")
        print(f"  Lifetime hours: {gene.get('total_lifetime_hours')}")

    # 15. Find gene matches
    print("\n=== Test 15: Find Gene Matches ===")
    r = requests.post(f"{BASE}/organism/gene/match", headers=h, json={
        "new_intelligence_data": {
            "species": "phone",
            "value": "13900139000",
            "threat_type": "fraud_phone",
            "related_entities": ["org-ip-192.168.1.1"]
        }
    })
    check("find_gene_matches", r)
    if r.status_code == 200:
        matches = r.json().get("matches", [])
        print(f"  Gene matches: {len(matches)}")
        for m in matches[:2]:
            print(f"    Gene {m.get('gene_id')[:12]}... species={m.get('species')}, patterns={m.get('patterns')}")

    # 16. Inherit genes
    print("\n=== Test 16: Inherit Genes ===")
    gene_id = None
    r_genes = requests.get(f"{BASE}/organism/genes", headers=h)
    if r_genes.status_code == 200:
        genes_list = r_genes.json().get("genes", [])
        if genes_list:
            gene_id = genes_list[0].get("gene_id")
    
    if gene_id:
        r = requests.post(f"{BASE}/organism/gene/inherit", headers=h, json={
            "new_organism_id": "org-phone-13900139000",
            "parent_gene_ids": [gene_id]
        })
        check("inherit_genes", r)
        if r.status_code == 200:
            inh = r.json()
            print(f"  Inherited vitality: {inh.get('initial_vitality')}")
            print(f"  Generation: {inh.get('generation')}")
            print(f"  Inherited patterns: {inh.get('patterns')}")
            print(f"  Inherited associations: {inh.get('associations')}")
    else:
        print("  ⚠️ No genes available to test inheritance")
        results["fail"] += 1
        results["errors"].append("No genes available for inheritance test")

    # 17. Get genealogy
    print("\n=== Test 17: Get Genealogy ===")
    r = requests.get(f"{BASE}/organism/genealogy/org-ip-192.168.1.1", headers=h)
    check("get_genealogy", r)
    if r.status_code == 200:
        gen = r.json()
        print(f"  Current generation: {gen.get('current_generation')}")
        print(f"  Total ancestors: {gen.get('total_ancestors')}")
        print(f"  Inherited patterns: {gen.get('inherited_patterns')}")

    # 18. List organisms
    print("\n=== Test 18: List Organisms ===")
    r = requests.get(f"{BASE}/organism/organisms?alive_only=false", headers=h)
    check("list_organisms", r)
    if r.status_code == 200:
        org_list = r.json()
        print(f"  Total organisms: {org_list.get('total')}")
        for o in org_list.get("organisms", [])[:3]:
            print(f"    {o.get('intelligence_id')}: species={o.get('species')}, alive={o.get('is_alive')}, vitality={o.get('vitality')}")

    # 19. List genes
    print("\n=== Test 19: List Genes ===")
    r = requests.get(f"{BASE}/organism/genes", headers=h)
    check("list_genes", r)
    if r.status_code == 200:
        gene_list = r.json()
        print(f"  Total genes: {gene_list.get('total')}")

    # 20. Run lifecycle check
    print("\n=== Test 20: Run Lifecycle Check ===")
    r = requests.post(f"{BASE}/organism/lifecycle-check", headers=h)
    check("lifecycle_check", r)
    if r.status_code == 200:
        lc = r.json()
        print(f"  Checked: {lc.get('checked')}")
        print(f"  Mutated: {lc.get('mutated')}")
        print(f"  Died: {lc.get('died')}")
        print(f"  Reborn: {lc.get('reborn')}")
        print(f"  Predictions validated: {lc.get('predictions_validated')}")

    # 21. Spawn with gene inheritance (rebirth scenario)
    print("\n=== Test 21: Spawn with Gene Inheritance (Rebirth) ===")
    if gene_id:
        r = requests.post(f"{BASE}/organism/spawn", headers=h, json={
            "intelligence_id": "org-phone-13900139000-reborn",
            "species": "phone",
            "initial_data": {
                "value": "13900139000",
                "threat_type": "fraud_phone",
                "confidence": 0.75,
                "related_entities": ["org-ip-192.168.1.1"]
            }
        })
        check("spawn_with_inheritance", r)
        if r.status_code == 200:
            reborn = r.json()
            print(f"  Generation: {reborn.get('generation')}")
            print(f"  Parent IDs: {reborn.get('parent_ids')}")
            print(f"  Inherited patterns in state: {reborn.get('current_state', {}).get('inherited_patterns', [])}")
    else:
        print("  ⚠️ Skipped - no genes available")

    # 22. Test invalid organism vitality
    print("\n=== Test 22: Invalid Organism Vitality ===")
    r = requests.get(f"{BASE}/organism/vitality/nonexistent-id", headers=h)
    check("invalid_organism_vitality", r)
    if r.status_code == 200:
        v = r.json()
        print(f"  Vitality for nonexistent: {v.get('vitality')}, Is alive: {v.get('is_alive')}")

    # 23. Test species-specific half-lives
    print("\n=== Test 23: Species Half-Life Verification ===")
    species_half_lives = {
        "ip": 72, "phone": 168, "bankcard": 336, "domain": 720,
        "ttp": 2160, "organization": 4320, "slang": 8760, "campaign": 720
    }
    for species, expected_hl in species_half_lives.items():
        r = requests.post(f"{BASE}/organism/spawn", headers=h, json={
            "intelligence_id": f"org-test-{species}",
            "species": species,
            "initial_data": {"value": f"test_{species}"}
        })
        if r.status_code == 200:
            org = r.json()
            actual_hl = org.get("half_life")
            if actual_hl == expected_hl:
                print(f"  ✅ {species}: half_life={actual_hl}h (expected {expected_hl}h)")
                results["pass"] += 1
            else:
                print(f"  ❌ {species}: half_life={actual_hl}h (expected {expected_hl}h)")
                results["fail"] += 1
        else:
            print(f"  ❌ {species}: spawn failed ({r.status_code})")
            results["fail"] += 1

    # 24. Test authentication requirement
    print("\n=== Test 24: Auth Required ===")
    r = requests.get(f"{BASE}/organism/organisms")
    if r.status_code == 401 or r.status_code == 403:
        print(f"  ✅ Unauthenticated access blocked ({r.status_code})")
        results["pass"] += 1
    else:
        print(f"  ❌ Unauthenticated access not blocked ({r.status_code})")
        results["fail"] += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"TOTAL: {results['pass']} passed, {results['fail']} failed")
    if results['errors']:
        print("\nErrors:")
        for e in results['errors']:
            print(e)
    return results

if __name__ == "__main__":
    test_organism_apis()
