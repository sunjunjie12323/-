"""
STIX 2.1 Exporter — Export threat intelligence in STIX format.
STIX (Structured Threat Information Expression) is the industry standard
for sharing cyber threat intelligence.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from loguru import logger


class STIXExporter:
    STIX_VERSION = "2.1"

    def export_intelligence(self, intel_data: Dict) -> Dict:
        objects = []
        indicator = self._create_indicator(intel_data)
        objects.append(indicator)
        if intel_data.get("threat_actor"):
            objects.append(self._create_threat_actor(intel_data))
        content = intel_data.get("content", "")
        cves = __import__('re').findall(r'CVE-\d{4}-\d{4,}', content)
        for cve in cves:
            objects.append(self._create_vulnerability(cve))
        malware_keywords = ["ransomware", "trojan", "backdoor", "worm", "rat"]
        if any(kw in content.lower() for kw in malware_keywords):
            objects.append(self._create_malware(intel_data))
        for i in range(1, len(objects)):
            objects.append(self._create_relationship(objects[0]["id"], objects[i]["id"], "related-to"))
        return {
            "type": "bundle",
            "id": f"bundle--{uuid.uuid4()}",
            "objects": objects,
        }

    def export_bundle(self, intel_list: List[Dict]) -> Dict:
        all_objects = []
        for intel in intel_list:
            bundle = self.export_intelligence(intel)
            all_objects.extend(bundle.get("objects", []))
        return {
            "type": "bundle",
            "id": f"bundle--{uuid.uuid4()}",
            "objects": all_objects,
        }

    def _create_indicator(self, intel: Dict) -> Dict:
        content = intel.get("content", "")
        threat_level = intel.get("threat_level", "info")
        confidence_map = {"critical": 95, "high": 80, "medium": 60, "low": 40, "info": 20}
        return {
            "type": "indicator",
            "spec_version": self.STIX_VERSION,
            "id": f"indicator--{uuid.uuid4()}",
            "created": intel.get("collected_at", datetime.now(timezone.utc).isoformat()),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": content[:80],
            "description": content,
            "confidence": confidence_map.get(threat_level, 50),
            "pattern": f"[file:hashes.'SHA-256' = '{intel.get('id', 'unknown')}']",
            "pattern_type": "stix",
            "valid_from": intel.get("collected_at", datetime.now(timezone.utc).isoformat()),
            "labels": [intel.get("entity_type", "threat-intelligence"), threat_level],
            "external_references": [
                {"source_name": "threat-intel-agent", "external_id": intel.get("id", "")}
            ],
        }

    def _create_threat_actor(self, intel: Dict) -> Dict:
        return {
            "type": "threat-actor",
            "spec_version": self.STIX_VERSION,
            "id": f"threat-actor--{uuid.uuid4()}",
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": intel.get("threat_actor", "Unknown"),
            "threat_actor_types": ["criminal"],
            "confidence": 70,
        }

    def _create_vulnerability(self, cve_id: str) -> Dict:
        return {
            "type": "vulnerability",
            "spec_version": self.STIX_VERSION,
            "id": f"vulnerability--{uuid.uuid4()}",
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": cve_id,
            "external_references": [
                {"source_name": "cve", "external_id": cve_id}
            ],
        }

    def _create_malware(self, intel: Dict) -> Dict:
        content = intel.get("content", "")
        return {
            "type": "malware",
            "spec_version": self.STIX_VERSION,
            "id": f"malware--{uuid.uuid4()}",
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": content[:50],
            "malware_types": ["ransomware"],
            "is_family": True,
        }

    def _create_relationship(self, source_id: str, target_id: str, rel_type: str) -> Dict:
        return {
            "type": "relationship",
            "spec_version": self.STIX_VERSION,
            "id": f"relationship--{uuid.uuid4()}",
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "relationship_type": rel_type,
            "source_ref": source_id,
            "target_ref": target_id,
        }

    def to_json(self, bundle: Dict, indent: int = 2) -> str:
        return json.dumps(bundle, ensure_ascii=False, indent=indent)
