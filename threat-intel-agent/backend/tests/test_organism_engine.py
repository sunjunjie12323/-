import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.intelligence_organism import (
    IntelligenceOrganismEngine,
    IntelligenceOrganism,
    IntelligenceGene,
    EvolutionEvent,
    VitalityReport,
    PredictionTracker,
    ValidationResult,
    SPECIES_HALF_LIFE_HOURS,
    DEATH_THRESHOLD,
)


def _make_mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="是")
    llm.generate_json = AsyncMock(return_value=[])
    llm.embed = AsyncMock(return_value=[0.1] * 1536)
    llm.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
    return llm


def _make_mock_vector_store():
    vs = AsyncMock()
    vs.search_intelligence = AsyncMock(return_value=[])
    vs.add_intelligence = AsyncMock(return_value=None)
    return vs


def _make_mock_knowledge_graph():
    kg = AsyncMock()
    kg.get_entity = AsyncMock(return_value=None)
    kg.add_entity = AsyncMock(return_value={"id": "test"})
    return kg


def _make_engine(tmp_dir=None):
    llm = _make_mock_llm()
    vs = _make_mock_vector_store()
    kg = _make_mock_knowledge_graph()
    kwargs = {}
    if tmp_dir:
        kwargs["persist_dir"] = tmp_dir
    engine = IntelligenceOrganismEngine(llm=llm, vector_store=vs, knowledge_graph=kg, **kwargs)
    return engine


passed = 0
failed = 0
errors = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        err = f"  ❌ {name}" + (f": {detail}" if detail else "")
        errors.append(err)
        print(err)


async def test_organism_engine():
    print("\n=== Test Suite: IntelligenceOrganismEngine ===\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        engine = _make_engine(tmp_dir)

        # 1. Spawn organism
        print("--- Spawn ---")
        org = await engine.spawn_organism("test-ip-1", "ip", {"value": "1.2.3.4", "threat_type": "c2"})
        check("spawn returns organism", org is not None)
        check("species is ip", org.species == "ip")
        check("generation is 1", org.generation == 1)
        check("is_alive", org.is_alive is True)
        check("vitality > 0", org.vitality > 0)
        check("half_life is 72", org.half_life == 72)
        check("evolution_log has born event", len(org.evolution_log) == 1)
        check("born event type", org.evolution_log[0].event_type == "born")
        check("organism stored in engine", "test-ip-1" in engine.organisms)

        # 2. Check vitality
        print("--- Vitality ---")
        report = await engine.check_vitality("test-ip-1")
        check("vitality report returned", report is not None)
        check("freshness > 0", report.freshness > 0)
        check("is_alive", report.is_alive is True)
        check("recommended_action is valid", report.recommended_action in [
            "no_action_needed", "monitor_normally", "schedule_refresh",
            "urgent_refresh_needed", "archive_and_preserve_genes"
        ])

        # 3. Evolve organism
        print("--- Evolve ---")
        evolved = await engine.evolve("test-ip-1", {"confidence": 0.95, "confirmed": True}, "test_trigger")
        check("evolve returns organism", evolved is not None)
        check("mention_count incremented", evolved.mention_count == 2)
        check("confirmed_use_count incremented", evolved.confirmed_use_count == 1)
        check("mutation detected", len(evolved.mutations) > 0)
        check("evolution log has 2 events", len(evolved.evolution_log) == 2)

        # 4. Non-existent organism
        print("--- Edge Cases ---")
        report = await engine.check_vitality("nonexistent")
        check("nonexistent vitality is 0", report.vitality == 0.0)
        check("nonexistent is_alive is False", report.is_alive is False)
        evolved_none = await engine.evolve("nonexistent", {})
        check("evolve nonexistent returns None", evolved_none is None)

        # 5. Species half-lives
        print("--- Species Half-Lives ---")
        for species, expected_hl in SPECIES_HALF_LIFE_HOURS.items():
            org = await engine.spawn_organism(f"test-{species}-hl", species, {"value": f"test_{species}"})
            check(f"{species} half_life={expected_hl}", org.half_life == expected_hl)

        # 6. Archive organism and gene preservation
        print("--- Archive & Genes ---")
        org = await engine.spawn_organism("test-phone-archive", "phone", {"value": "13800138000"})
        await engine.evolve("test-phone-archive", {"confirmed": True, "new_data": "test"}, "test")
        gene = await engine.archive_organism("test-phone-archive", cause="test_expired")
        check("gene returned", gene is not None)
        check("gene has gene_id", len(gene.gene_id) > 0)
        check("gene species is phone", gene.species == "phone")
        check("gene has patterns", len(gene.patterns) > 0)
        check("gene cause_of_death", gene.cause_of_death == "test_expired")
        check("organism is dead after archive", engine.organisms["test-phone-archive"].is_alive is False)
        check("gene stored in engine", gene.gene_id in engine.genes)

        # 7. Gene matching
        print("--- Gene Matching ---")
        matches = await engine.find_gene_matches({"species": "phone", "value": "13900139000"})
        check("gene matches found", len(matches) > 0)
        check("best match is phone species", matches[0].species == "phone")

        # 8. Gene inheritance
        print("--- Gene Inheritance ---")
        result = await engine.inherit_genes("new-org-phone", [gene.gene_id])
        check("inheritance returns dict", isinstance(result, dict))
        check("generation >= 2", result["generation"] >= 2)
        check("inherited patterns", len(result.get("patterns", [])) > 0)

        # 9. Spawn with gene inheritance
        print("--- Spawn with Inheritance ---")
        org_reborn = await engine.spawn_organism("test-phone-reborn", "phone", {"value": "13900139000", "species": "phone"})
        check("reborn organism generation >= 2", org_reborn.generation >= 2,
              f"got generation={org_reborn.generation}")

        # 10. Prediction registration and validation
        print("--- Predictions ---")
        tracker = await engine.register_prediction(
            "test-ip-1",
            [
                {"action": "domain_registration", "probability": 0.7},
                {"action": "phishing_campaign", "probability": 0.3},
            ],
            validation_window_hours=168,
        )
        check("prediction tracker returned", tracker is not None)
        check("tracker has prediction_id", len(tracker.prediction_id) > 0)
        check("tracker has 2 steps", len(tracker.predicted_steps) == 2)
        check("tracker has deadline", len(tracker.validation_deadline) > 0)

        validations = await engine.validate_predictions()
        check("validate_predictions returns list", isinstance(validations, list))

        accuracy = await engine.get_prediction_accuracy()
        check("accuracy report returned", accuracy is not None)
        check("accuracy has brier_score", hasattr(accuracy, "brier_score"))

        calibration = await engine.calibrate_model()
        check("calibration result returned", calibration is not None)
        check("calibration has bias_direction", hasattr(calibration, "bias_direction"))

        # 11. Evolution timeline
        print("--- Timeline ---")
        timeline = await engine.get_evolution_timeline("test-ip-1")
        check("timeline has events", len(timeline) > 0)
        check("first event is born", timeline[0].event_type == "born")

        # 12. Genealogy
        print("--- Genealogy ---")
        genealogy = await engine.get_genealogy("test-phone-reborn")
        check("genealogy returned", genealogy is not None)
        check("genealogy current_generation >= 1", genealogy.current_generation >= 1)

        # 13. Offspring tree
        print("--- Offspring ---")
        tree = await engine.find_offspring("test-ip-1", depth=2)
        check("offspring tree returned", tree is not None)
        check("tree has root_id", tree.root_id == "test-ip-1")

        # 14. Lifecycle check
        print("--- Lifecycle ---")
        result = await engine.run_lifecycle_check()
        check("lifecycle check returns dict", isinstance(result, dict))
        check("lifecycle has checked key", "checked" in result)

        # 15. Persistence
        print("--- Persistence ---")
        await engine.save_to_disk()
        persist_path = Path(tmp_dir) / "organism_state.json"
        check("persist file created", persist_path.exists())

        with open(persist_path, "r") as f:
            saved_data = json.load(f)
        check("saved data has organisms", "organisms" in saved_data)
        check("saved data has genes", "genes" in saved_data)
        check("saved organisms count matches", len(saved_data["organisms"]) == len(engine.organisms))
        check("saved genes count matches", len(saved_data["genes"]) == len(engine.genes))

        # 16. Load from disk
        engine2 = _make_engine(tmp_dir)
        check("loaded organisms match", len(engine2.organisms) == len(engine.organisms))
        check("loaded genes match", len(engine2.genes) == len(engine.genes))
        check("loaded organism species preserved",
              engine2.organisms.get("test-ip-1") is not None and
              engine2.organisms["test-ip-1"].species == "ip")

        # 17. Field change magnitude
        print("--- Field Change Detection ---")
        mag = engine._field_change_magnitude(0.5, 0.9)
        check("numeric change detected", mag > 0)
        mag_same = engine._field_change_magnitude("hello", "hello")
        check("same string = 0 change", mag_same == 0.0)
        mag_new = engine._field_change_magnitude(None, "new_value")
        check("None to value = 1.0", mag_new == 1.0)

        # 18. Vitality formula
        print("--- Vitality Formula ---")
        org_fresh = await engine.spawn_organism("test-vitality-fresh", "ip", {"value": "10.0.0.1"})
        report = await engine.check_vitality("test-vitality-fresh")
        check("fresh organism vitality > 0.3", report.vitality > 0.3, f"got {report.vitality}")
        check("freshness close to 1.0", report.freshness > 0.9)


async def test_security():
    print("\n=== Test Suite: Security ===\n")

    from app.config import Settings

    with tempfile.TemporaryDirectory() as tmp_dir:
        env_file = Path(tmp_dir) / ".env"
        env_file.write_text("SECRET_KEY=\n")

        s = Settings(_env_file=str(env_file))
        key = s.secret_key_resolved
        check("auto-generated key is not empty", len(key) > 0)
        check("auto-generated key is not default", key != "change-me-in-production-use-a-strong-random-key")
        check("auto-generated key length > 30", len(key) > 30)

        key2 = s.secret_key_resolved
        check("same key on second call", key == key2)

    default_settings = Settings()
    default_cors = default_settings.cors_origins_list
    check("CORS does not include 3000", "http://localhost:3000" not in default_cors)
    check("CORS does not include 3001", "http://localhost:3001" not in default_cors)
    check("CORS does not include 3002", "http://localhost:3002" not in default_cors)


async def main():
    await test_organism_engine()
    await test_security()

    print("\n" + "=" * 60)
    print(f"UNIT TESTS: {passed} passed, {failed} failed")
    if errors:
        print("\nFailures:")
        for e in errors:
            print(e)


if __name__ == "__main__":
    asyncio.run(main())
