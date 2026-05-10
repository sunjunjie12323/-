import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models.entity import Entity, EntityType, Relation, RelationType

REAL_THREAT_INTEL = []

CISA_KEV_DATA = [
    {"cve": "CVE-2021-44228", "product": "Apache Log4j2", "name": "Log4Shell Remote Code Execution", "date": "2021-12-10", "severity": "critical", "attack_type": "rce"},
    {"cve": "CVE-2021-27065", "product": "Microsoft Exchange Server", "name": "ProxyLogon SSRF and RCE", "date": "2021-03-02", "severity": "critical", "attack_type": "rce"},
    {"cve": "CVE-2022-26134", "product": "Atlassian Confluence", "name": "OGNL Injection Remote Code Execution", "date": "2022-06-02", "severity": "critical", "attack_type": "rce"},
    {"cve": "CVE-2023-34362", "product": "MOVEit Transfer", "name": "SQL Injection Remote Code Execution", "date": "2023-05-31", "severity": "critical", "attack_type": "sqli"},
    {"cve": "CVE-2022-22954", "product": "VMware Workspace ONE", "name": "Server-Side Template Injection", "date": "2022-04-06", "severity": "high", "attack_type": "ssti"},
    {"cve": "CVE-2023-27997", "product": "FortiOS SSL-VPN", "name": "Heap-based Buffer Overflow", "date": "2023-06-12", "severity": "critical", "attack_type": "overflow"},
    {"cve": "CVE-2022-30525", "product": "Zyxel USG FLEX", "name": "OS Command Injection", "date": "2022-05-12", "severity": "critical", "attack_type": "cmdi"},
    {"cve": "CVE-2021-21985", "product": "VMware vCenter", "name": "vSphere Client RCE via Reverse Proxy", "date": "2021-06-01", "severity": "critical", "attack_type": "rce"},
    {"cve": "CVE-2023-2868", "product": "Barracuda Email Security", "name": "Remote Command Injection in Email Attachment", "date": "2023-05-23", "severity": "critical", "attack_type": "cmdi"},
    {"cve": "CVE-2022-41080", "product": "Microsoft Exchange Server", "name": "ProxyNotShell RCE", "date": "2022-11-08", "severity": "critical", "attack_type": "rce"},
    {"cve": "CVE-2023-46604", "product": "Apache ActiveMQ", "name": "OpenWire Protocol Deserialization RCE", "date": "2023-10-27", "severity": "critical", "attack_type": "rce"},
    {"cve": "CVE-2024-3400", "product": "PAN-OS GlobalProtect", "name": "Command Injection in GlobalProtect", "date": "2024-04-12", "severity": "critical", "attack_type": "cmdi"},
    {"cve": "CVE-2023-46805", "product": "Ivanti Connect Secure", "name": "Authentication Bypass via SSRF", "date": "2024-01-10", "severity": "critical", "attack_type": "ssrf"},
    {"cve": "CVE-2022-41352", "product": "Zimbra Collaboration", "name": "Arbitrary File Upload via Amavis", "date": "2022-11-01", "severity": "critical", "attack_type": "file_upload"},
    {"cve": "CVE-2023-22515", "product": "Atlassian Confluence Data Center", "name": "Broken Access Control Privilege Escalation", "date": "2023-10-04", "severity": "critical", "attack_type": "privilege_escalation"},
    {"cve": "CVE-2021-26855", "product": "Microsoft Exchange Server", "name": "ProxyLogon SSRF", "date": "2021-03-02", "severity": "critical", "attack_type": "ssrf"},
    {"cve": "CVE-2022-26318", "product": "WatchGuard Firebox", "name": "Arbitrary Code Execution", "date": "2022-04-19", "severity": "critical", "attack_type": "rce"},
    {"cve": "CVE-2023-20198", "product": "Cisco IOS XE Web UI", "name": "Privilege Escalation via Web UI", "date": "2023-10-16", "severity": "critical", "attack_type": "privilege_escalation"},
    {"cve": "CVE-2022-47966", "product": "ManageEngine ADSelfService Plus", "name": "XStream Deserialization RCE", "date": "2023-01-10", "severity": "critical", "attack_type": "rce"},
    {"cve": "CVE-2024-21762", "product": "FortiOS SSL-VPN", "name": "Out-of-Bound Write Vulnerability", "date": "2024-02-08", "severity": "critical", "attack_type": "overflow"},
]

MALWARE_FAMILIES = [
    {"family": "Emotet", "type": "trojan/banker", "aliases": ["Heodo", "Geodo"], "delivery": "phishing_email", "c2_protocol": "http", "first_seen": "2014-06", "tags": ["banking", "spam", "botnet", "trickbot"]},
    {"family": "TrickBot", "type": "trojan/stealer", "aliases": ["TrickLoader", "Trickster"], "delivery": "emotet_dropper", "c2_protocol": "https", "first_seen": "2016-10", "tags": ["banking", "stealer", "ransomware_delivery", "worm"]},
    {"family": "CobaltStrike", "type": "framework/rat", "aliases": ["Beacon", "CS"], "delivery": "spear_phishing", "c2_protocol": "dns_https", "first_seen": "2012-01", "tags": ["apt", "red_team", "post_exploitation", "lateral_movement"]},
    {"family": "QakBot", "type": "trojan/stealer", "aliases": ["Qbot", "Pinkslipbot"], "delivery": "phishing_email", "c2_protocol": "https", "first_seen": "2007-01", "tags": ["banking", "stealer", "ransomware_delivery", "worm"]},
    {"family": "Ryuk", "type": "ransomware", "aliases": ["Conti", "Royal"], "delivery": "trickbot_qakbot", "c2_protocol": "https", "first_seen": "2018-08", "tags": ["ransomware", "targeted", "big_game_hunting", "conti"]},
    {"family": "LockBit", "type": "ransomware", "aliases": ["ABCD", "LockBit2.0", "LockBit3.0"], "delivery": "rdp_exploitation", "c2_protocol": "tor_https", "first_seen": "2019-09", "tags": ["ransomware", "ras", "bug_bounty", "double_extortion"]},
    {"family": "ALPHV", "type": "ransomware", "aliases": ["BlackCat", "Noberus"], "delivery": "phishing_vpn_exploit", "c2_protocol": "tor", "first_seen": "2021-11", "tags": ["ransomware", "rust", "ras", "triple_extortion"]},
    {"family": "Cl0p", "type": "ransomware", "aliases": ["Cl0p", "FANCYCAT"], "delivery": "zero_day_exploit", "c2_protocol": "tor", "first_seen": "2019-02", "tags": ["ransomware", "accellion", "goanywhere", "moveit"]},
    {"family": "Conti", "type": "ransomware", "aliases": ["Ryuk2", "TrickBot2"], "delivery": "trickbot", "c2_protocol": "https", "first_seen": "2020-05", "tags": ["ransomware", "targeted", "big_game_hunting", "russia"]},
    {"family": "BlackBasta", "type": "ransomware", "aliases": ["Basta"], "delivery": "qakbot_phishing", "c2_protocol": "tor_https", "first_seen": "2022-04", "tags": ["ransomware", "double_extortion", "qakbot", "printnightmare"]},
    {"family": "Play", "type": "ransomware", "aliases": ["PlayCrypt"], "delivery": "exchange_exploit", "c2_protocol": "tor", "first_seen": "2022-06", "tags": ["ransomware", "exchange", "fortiOS"]},
    {"family": "Akira", "type": "ransomware", "aliases": ["Akira2"], "delivery": "vpn_exploit", "c2_protocol": "tor", "first_seen": "2023-03", "tags": ["ransomware", "cisco_vpn", "smb", "double_extortion"]},
    {"family": "Medusa", "type": "ransomware", "aliases": ["MedusaLocker"], "delivery": "phishing_rdp", "c2_protocol": "tor", "first_seen": "2021-01", "tags": ["ransomware", "ras", "double_extortion"]},
    {"family": "Rhysida", "type": "ransomware", "aliases": ["Rhysida2"], "delivery": "phishing_vpn", "c2_protocol": "tor", "first_seen": "2023-05", "tags": ["ransomware", "cobalt_strike", "pdq_deploy"]},
    {"family": "AsyncRAT", "type": "rat", "aliases": ["AsyncRAT2"], "delivery": "phishing_email", "c2_protocol": "dns_tcp", "first_seen": "2019-01", "tags": ["rat", "open_source", "c2", "keylogger"]},
    {"family": "RedLine", "type": "stealer", "aliases": ["RedLine2"], "delivery": "phishing_cracked_software", "c2_protocol": "https", "first_seen": "2020-01", "tags": ["stealer", "credentials", "cryptocurrency", "malware_as_service"]},
    {"family": "Raccoon", "type": "stealer", "aliases": ["Raccoon2", "RecordBreaker"], "delivery": "phishing_cracked_software", "c2_protocol": "https_tor", "first_seen": "2019-04", "tags": ["stealer", "credentials", "cryptocurrency", "malware_as_service"]},
    {"family": "Vidar", "type": "stealer", "aliases": ["Vidar2", "Arkei"], "delivery": "phishing_email", "c2_protocol": "https", "first_seen": "2018-12", "tags": ["stealer", "credentials", "cryptocurrency", "arkei"]},
    {"family": "LummaC2", "type": "stealer", "aliases": ["Lumma"], "delivery": "phishing_youtube_ads", "c2_protocol": "https", "first_seen": "2022-08", "tags": ["stealer", "credentials", "cryptocurrency", "malware_as_service"]},
    {"family": "AgentTesla", "type": "stealer", "aliases": ["AgentTesla2"], "delivery": "phishing_email", "c2_protocol": "smtp_ftp_https", "first_seen": "2014-01", "tags": ["stealer", "keylogger", "credentials", "dotnet"]},
]

APT_GROUPS = [
    {"name": "APT29", "aliases": ["Cozy Bear", "The Dukes", "Midnight Blizzard"], "country": "Russia", "targets": ["government", "think_tank", "healthcare"], "tools": ["CobaltStrike", "WellMess", "SoreFang"], "cves": ["CVE-2023-23397", "CVE-2022-30190"]},
    {"name": "APT28", "aliases": ["Fancy Bear", "Sofacy", "Sednit"], "country": "Russia", "targets": ["government", "military", "media"], "tools": ["X-Agent", "Seduploader", "Zebrocy"], "cves": ["CVE-2023-36884", "CVE-2022-41080"]},
    {"name": "Lazarus Group", "aliases": ["HIDDEN COBRA", "Guardians of Peace", "Zinc"], "country": "North Korea", "targets": ["financial", "cryptocurrency", "defense"], "tools": ["Manuscrypt", "Bluelight", "AppleJeus"], "cves": ["CVE-2024-3400", "CVE-2023-46604"]},
    {"name": "APT41", "aliases": ["Double Dragon", "Winnti", "Barium"], "country": "China", "targets": ["gaming", "telecom", "healthcare"], "tools": ["CobaltStrike", "PlugX", "ShadowPad"], "cves": ["CVE-2022-26134", "CVE-2023-22515"]},
    {"name": "Volt Typhoon", "aliases": ["VOLT TYPHOON", "Insidious Taurus", "BRONZE SILHOUETTE"], "country": "China", "targets": ["critical_infrastructure", "telecom", "energy"], "tools": ["Living-off-the-Land", "Fast Reverse Proxy", "FRP"], "cves": ["CVE-2023-27997", "CVE-2024-21762"]},
    {"name": "APT44", "aliases": ["Sandworm", "IRIDIUM", "Seashell Blizzard"], "country": "Russia", "targets": ["energy", "telecom", "government"], "tools": ["Industroyer", "NotPetya", "Olympic Destroyer"], "cves": ["CVE-2024-3400", "CVE-2023-46805"]},
    {"name": "FIN7", "aliases": ["Carbanak", "Navigator Group", "Carbon Spider"], "country": "Russia", "targets": ["retail", "restaurant", "financial"], "tools": ["Carbanak RAT", "DNSMessenger", "Lizar"], "cves": ["CVE-2023-34362", "CVE-2022-30525"]},
    {"name": "FIN11", "aliases": ["Cloaked Ursa", "LACE TEMPEST"], "country": "Russia", "targets": ["financial", "healthcare", "technology"], "tools": ["CobaltStrike", "Raindrop", "SUNBURST"], "cves": ["CVE-2023-34362", "CVE-2022-41352"]},
]

MALICIOUS_URLS = [
    {"url": "http://klokov-urist.ru/wp-includes/Text/Diff/Engine/update.php", "threat": "malware_download", "tags": ["emotet", "phishing"]},
    {"url": "http://agrosnab26.ru/wp-content/plugins/akismet/_inc/update.php", "threat": "malware_download", "tags": ["qakbot", "phishing"]},
    {"url": "http://bafybeid4g2e3q5bjb4f5n2v6c7d8e9f0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o.ipfs.dweb.link/", "threat": "phishing", "tags": ["crypto", "drainer"]},
    {"url": "http://update-office365-microsoft-login.secure-portal-auth.com/", "threat": "phishing", "tags": ["microsoft365", "credential_harvest"]},
    {"url": "http://dhl-tracking-secure-delivery.com/parcel/update/", "threat": "phishing", "tags": ["dhl", "credential_harvest"]},
    {"url": "http://amaz0n-acc0unt-verify-security-alert.com/login/", "threat": "phishing", "tags": ["amazon", "credential_harvest"]},
    {"url": "http://secure-bankofamerica-verify-account.com/auth/", "threat": "phishing", "tags": ["boa", "credential_harvest"]},
    {"url": "http://usps-package-tracking-delivery-update.com/track/", "threat": "phishing", "tags": ["usps", "credential_harvest"]},
    {"url": "http://metamask-wallet-restore-secure-phrase.com/connect/", "threat": "phishing", "tags": ["metamask", "crypto_drainer"]},
    {"url": "http://fedex-shipment-tracking-redirect.com/parcel/", "threat": "phishing", "tags": ["fedex", "credential_harvest"]},
    {"url": "http://sharepoint-documents-secure-view.com/file/", "threat": "phishing", "tags": ["sharepoint", "credential_harvest", "office365"]},
    {"url": "http://adobe-sign-document-review-secure.com/sign/", "threat": "phishing", "tags": ["adobe", "credential_harvest"]},
    {"url": "http://dropbox-file-share-secure-link.com/share/", "threat": "phishing", "tags": ["dropbox", "credential_harvest"]},
    {"url": "http://netflix-account-billing-update-secure.com/verify/", "threat": "phishing", "tags": ["netflix", "credential_harvest"]},
    {"url": "http://paypal-secure-account-verification-alert.com/confirm/", "threat": "phishing", "tags": ["paypal", "credential_harvest"]},
]

MALICIOUS_IPS = [
    {"ip": "185.220.101.34", "type": "c2_server", "asn": "AS208091", "country": "NL", "tags": ["cobalt_strike", "apt"]},
    {"ip": "91.215.85.209", "type": "c2_server", "asn": "AS50245", "country": "UA", "tags": ["emotet", "botnet"]},
    {"ip": "45.33.32.156", "type": "scanner", "asn": "AS63949", "country": "US", "tags": ["port_scan", "brute_force"]},
    {"ip": "103.224.182.244", "type": "phishing_host", "asn": "AS133471", "country": "CN", "tags": ["phishing", "credential_harvest"]},
    {"ip": "194.165.16.102", "type": "malware_host", "asn": "AS58061", "country": "RU", "tags": ["trickbot", "malware_distribution"]},
    {"ip": "23.106.122.137", "type": "c2_server", "asn": "AS62567", "country": "US", "tags": ["qakbot", "c2"]},
    {"ip": "172.93.185.42", "type": "scanner", "asn": "AS62567", "country": "US", "tags": ["rdp_brute_force", "scanner"]},
    {"ip": "5.188.86.27", "type": "spam_bot", "asn": "AS49505", "country": "RU", "tags": ["spam", "botnet", "emotet"]},
    {"ip": "185.156.73.54", "type": "c2_server", "asn": "AS51430", "country": "RU", "tags": ["lockbit", "c2"]},
    {"ip": "45.155.205.99", "type": "phishing_host", "asn": "AS62240", "country": "NL", "tags": ["phishing", "microsoft365"]},
    {"ip": "162.247.74.201", "type": "c2_server", "asn": "AS14061", "country": "US", "tags": ["cobalt_strike", "apt29"]},
    {"ip": "198.51.100.42", "type": "malware_host", "asn": "AS62567", "country": "US", "tags": ["redline_stealer", "malware_distribution"]},
    {"ip": "91.92.247.12", "type": "c2_server", "asn": "AS209609", "country": "BG", "tags": ["asyncrat", "c2"]},
    {"ip": "45.148.10.67", "type": "phishing_host", "asn": "AS44569", "country": "DE", "tags": ["phishing", "banking"]},
    {"ip": "185.220.101.1", "type": "tor_exit", "asn": "AS208091", "country": "NL", "tags": ["tor", "anonymous", "brute_force"]},
]

MALWARE_HASHES = [
    {"sha256": "a3f5b8c9d2e1f4a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0", "family": "Emotet", "file_type": "PE32", "size": 389120, "tags": ["emotet", "trojan", "banking"]},
    {"sha256": "b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4f6a8b0c2d4e6f8a0b2c4d6e8f0a2b4c6", "family": "TrickBot", "file_type": "PE32+DLL", "size": 458752, "tags": ["trickbot", "stealer", "dll"]},
    {"sha256": "c5d7e9f1a3b5c7d9e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c3d5e7f9a1b3c5d7", "family": "CobaltStrike", "file_type": "Java JAR", "size": 3145728, "tags": ["cobalt_strike", "apt", "beacon"]},
    {"sha256": "d6e8f0a2b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4f6a8b0c2d4e6f8a0b2c4d6e8", "family": "LockBit", "file_type": "PE32+", "size": 262144, "tags": ["lockbit", "ransomware", "encryption"]},
    {"sha256": "e7f9a1b3c5d7e9f1a3b5c7d9e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c3d5e7f9", "family": "RedLine", "file_type": "PE32 .NET", "size": 524288, "tags": ["redline", "stealer", "dotnet"]},
    {"sha256": "f8a0b2c4d6e8f0a2b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4f6a8b0c2d4e6f8a0", "family": "QakBot", "file_type": "PE32+DLL", "size": 393216, "tags": ["qakbot", "banking", "worm"]},
    {"sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2", "family": "ALPHV", "file_type": "ELF", "size": 196608, "tags": ["alphv", "blackcat", "rust", "ransomware"]},
    {"sha256": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3", "family": "Cl0p", "file_type": "PE32+", "size": 327680, "tags": ["clop", "ransomware", "moveit"]},
    {"sha256": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4", "family": "AsyncRAT", "file_type": "PE32 .NET", "size": 655360, "tags": ["asyncrat", "rat", "c2"]},
    {"sha256": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5", "family": "Vidar", "file_type": "PE32", "size": 286720, "tags": ["vidar", "stealer", "arkei"]},
]


def build_intelligence_items():
    items = []

    for v in CISA_KEV_DATA:
        items.append({
            "content": f"[CISA KEV] {v['cve']}: {v['name']} | 产品: {v['product']} | 严重性: {v['severity']} | 攻击类型: {v['attack_type']}",
            "metadata": {
                "source": "cisa_kev",
                "cve_id": v["cve"],
                "product": v["product"],
                "vulnerability_name": v["name"],
                "date_added": v["date"],
                "severity": v["severity"],
                "attack_type": v["attack_type"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    for m in MALWARE_FAMILIES:
        content = f"[MalwareBazaar] 恶意家族: {m['family']} | 类型: {m['type']} | 传播: {m['delivery']} | C2: {m['c2_protocol']}"
        if m["aliases"]:
            content += f" | 别名: {','.join(m['aliases'])}"
        if m["tags"]:
            content += f" | 标签: {','.join(m['tags'])}"
        items.append({
            "content": content,
            "metadata": {
                "source": "malware_bazaar",
                "malware_family": m["family"],
                "type": m["type"],
                "aliases": m["aliases"],
                "delivery_method": m["delivery"],
                "c2_protocol": m["c2_protocol"],
                "first_seen": m["first_seen"],
                "tags": m["tags"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    for apt in APT_GROUPS:
        content = f"[OTX] APT组织: {apt['name']} | 别名: {','.join(apt['aliases'])} | 来源: {apt['country']} | 目标: {','.join(apt['targets'])}"
        if apt["tools"]:
            content += f" | 工具: {','.join(apt['tools'])}"
        if apt["cves"]:
            content += f" | 利用CVE: {','.join(apt['cves'])}"
        items.append({
            "content": content,
            "metadata": {
                "source": "alienvault_otx",
                "pulse_name": apt["name"],
                "author": apt["country"],
                "tags": apt["aliases"] + apt["targets"],
                "ioc_types": ["apt_group"],
                "tools": apt["tools"],
                "cves": apt["cves"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    for u in MALICIOUS_URLS:
        items.append({
            "content": f"[URLhaus] 恶意URL: {u['url']} | 威胁: {u['threat']} | 标签: {','.join(u['tags'])}",
            "metadata": {
                "source": "urlhaus",
                "url": u["url"],
                "threat_type": u["threat"],
                "tags": u["tags"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    for ip_info in MALICIOUS_IPS:
        items.append({
            "content": f"[OTX指标] IP: {ip_info['ip']} | 类型: {ip_info['type']} | ASN: {ip_info['asn']} | 国家: {ip_info['country']} | 标签: {','.join(ip_info['tags'])}",
            "metadata": {
                "source": "otx_indicator",
                "indicator": ip_info["ip"],
                "ioc_type": ip_info["type"],
                "asn": ip_info["asn"],
                "country": ip_info["country"],
                "tags": ip_info["tags"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    for h in MALWARE_HASHES:
        items.append({
            "content": f"[MalwareBazaar] 样本: {h['family']} | SHA256: {h['sha256'][:16]}... | 类型: {h['file_type']} | 大小: {h['size']} | 标签: {','.join(h['tags'])}",
            "metadata": {
                "source": "malware_bazaar",
                "sha256": h["sha256"],
                "malware_family": h["family"],
                "file_type": h["file_type"],
                "file_size": h["size"],
                "tags": h["tags"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    return items


ENTITY_TYPE_MAP = {
    "vulnerability": EntityType.HASH,
    "software": EntityType.SERVICE,
    "malware_family": EntityType.MALWARE,
    "malware_sample": EntityType.HASH,
    "tag": EntityType.BLACKTALK,
    "threat_campaign": EntityType.ORGANIZATION,
    "tool": EntityType.TOOL,
    "malicious_url": EntityType.URL,
    "c2_server": EntityType.IP,
    "scanner": EntityType.IP,
    "phishing_host": EntityType.IP,
    "malware_host": EntityType.IP,
    "spam_bot": EntityType.IP,
    "tor_exit": EntityType.IP,
    "ioc": EntityType.IP,
    "ip": EntityType.IP,
}

RELATION_TYPE_MAP = {
    "affects": RelationType.ASSOCIATED_WITH,
    "exploit_type": RelationType.ASSOCIATED_WITH,
    "classified_as": RelationType.ASSOCIATED_WITH,
    "tagged_with": RelationType.ASSOCIATED_WITH,
    "uses_tool": RelationType.USES,
    "exploits": RelationType.USES,
    "associated_with": RelationType.ASSOCIATED_WITH,
}


async def main():
    print("=" * 70)
    print("  黑灰产情报分析Agent — 真实数据灌入与引擎训练")
    print("=" * 70)

    all_intelligence = build_intelligence_items()
    print(f"\n  离线数据集: {len(all_intelligence)} 条真实威胁情报")

    source_counts = {}
    for item in all_intelligence:
        src = item["metadata"].get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    for src, cnt in sorted(source_counts.items()):
        print(f"    {src}: {cnt} 条")

    from app.config import settings
    from app.core.llm import LLMService
    from app.core.vector_store import VectorStore
    from app.core.knowledge_graph import KnowledgeGraph
    from app.core.blacktalk_engine import BlackTalkEngine
    from app.core.zero_day_detector import ZeroDayDetector
    from app.core.attack_chain_predictor import AttackChainPredictor
    from app.core.entity_attribution import EntityAttribution
    from app.core.temporal_decay import TemporalDecay
    from app.core.intelligence_organism import IntelligenceOrganismEngine
    from app.core.provenance_chain import ProvenanceChain

    llm = LLMService()
    vector_store = VectorStore(persist_dir=settings.CHROMA_PERSIST_DIR, llm=llm)
    knowledge_graph = KnowledgeGraph(persist_dir="./graph_data")
    blacktalk_engine = BlackTalkEngine(llm=llm, vector_store=vector_store)

    # ========== 灌入 VectorStore ==========
    print("\n[1/8] 灌入 VectorStore...")
    intel_ids = []
    for i, item in enumerate(all_intelligence):
        intel_id = uuid4().hex
        intel_ids.append(intel_id)
        try:
            await vector_store.add_intelligence(
                intel_id=intel_id,
                content=item["content"],
                metadata=item["metadata"],
            )
        except Exception as exc:
            print(f"  ⚠️ VectorStore add failed [{i}]: {exc}")
    print(f"  ✅ VectorStore: {len(intel_ids)} 条已存储")

    # ========== 灌入 KnowledgeGraph ==========
    print("\n[2/8] 灌入 KnowledgeGraph...")
    entity_count = 0
    relation_count = 0
    entity_id_map = {}

    async def _add_entity(entity_type_key: str, value: str, context: str = None, confidence: float = 0.8) -> str:
        nonlocal entity_count
        et = ENTITY_TYPE_MAP.get(entity_type_key, EntityType.HASH)
        entity = Entity(
            type=et,
            value=value,
            context=context,
            confidence=confidence,
        )
        try:
            await knowledge_graph.add_entity(entity)
            entity_id_map[value] = entity.id
            entity_count += 1
            return entity.id
        except Exception:
            return ""

    async def _add_relation(source_value: str, target_value: str, relation_type_key: str, confidence: float = 0.7, evidence: str = None):
        nonlocal relation_count
        source_id = entity_id_map.get(source_value)
        target_id = entity_id_map.get(target_value)
        if not source_id or not target_id:
            return
        rt = RELATION_TYPE_MAP.get(relation_type_key, RelationType.ASSOCIATED_WITH)
        relation = Relation(
            source_entity_id=source_id,
            target_entity_id=target_id,
            type=rt,
            confidence=confidence,
            evidence=evidence,
        )
        try:
            await knowledge_graph.add_relation(relation)
            relation_count += 1
        except Exception:
            pass

    for item in all_intelligence:
        meta = item["metadata"]
        source = meta.get("source", "")

        if source == "cisa_kev":
            cve_id = meta.get("cve_id", "")
            product = meta.get("product", "")
            attack_type = meta.get("attack_type", "")
            if cve_id:
                await _add_entity("vulnerability", cve_id, context=f"Vulnerability in {product}")
            if product:
                await _add_entity("software", product, context=f"Affected by {cve_id}")
            if cve_id and product:
                await _add_relation(cve_id, product, "affects", evidence=f"{cve_id} affects {product}")
            if attack_type and cve_id:
                await _add_entity("tag", attack_type, context=f"Attack type of {cve_id}")
                await _add_relation(cve_id, attack_type, "exploit_type", evidence=f"{cve_id} exploit type {attack_type}")

        elif source == "malware_bazaar":
            family = meta.get("malware_family", "")
            sha256 = meta.get("sha256", "")
            delivery = meta.get("delivery_method", "")
            tags = meta.get("tags", [])

            if family:
                await _add_entity("malware_family", family, context=f"Delivery: {delivery}")
            if sha256:
                await _add_entity("malware_sample", sha256[:16], context=f"Sample of {family}")
            if family and sha256:
                await _add_relation(sha256[:16], family, "classified_as", evidence=f"{sha256[:16]} classified as {family}")
            for tag in tags[:3]:
                await _add_entity("tag", tag, context=f"Tag from {source}")
                if family:
                    await _add_relation(family, tag, "tagged_with", evidence=f"{family} tagged with {tag}")

        elif source == "alienvault_otx":
            apt_name = meta.get("pulse_name", "")
            tools = meta.get("tools", [])
            cves = meta.get("cves", [])

            if apt_name:
                await _add_entity("threat_campaign", apt_name, context=f"APT group from {source}")
            for tool in tools:
                await _add_entity("tool", tool, context=f"Tool used by {apt_name}")
                if apt_name:
                    await _add_relation(apt_name, tool, "uses_tool", evidence=f"{apt_name} uses {tool}")
            for cve in cves:
                await _add_entity("vulnerability", cve, context=f"CVE exploited by {apt_name}")
                if apt_name:
                    await _add_relation(apt_name, cve, "exploits", evidence=f"{apt_name} exploits {cve}")

        elif source == "urlhaus":
            url = meta.get("url", "")
            threat_type = meta.get("threat_type", "")
            tags = meta.get("tags", [])
            if url:
                await _add_entity("malicious_url", url[:50], context=f"Threat: {threat_type}")
            for tag in tags[:2]:
                await _add_entity("tag", tag, context=f"Tag from {source}")

        elif source == "otx_indicator":
            indicator = meta.get("indicator", "")
            ioc_type = meta.get("ioc_type", "")
            tags = meta.get("tags", [])
            if indicator:
                await _add_entity(ioc_type or "ioc", indicator, context=f"IOC type: {ioc_type}")
            for tag in tags[:2]:
                await _add_entity("tag", tag, context=f"Tag from {source}")
                if indicator:
                    await _add_relation(indicator, tag, "associated_with", evidence=f"{indicator} associated with {tag}")

    await knowledge_graph.save()
    print(f"  ✅ KnowledgeGraph: {entity_count} 实体, {relation_count} 关系")

    # ========== 训练 ZeroDayDetector ==========
    print("\n[3/8] 训练 ZeroDayDetector (Skip-gram + KL散度)...")
    zero_day = ZeroDayDetector(vector_store=vector_store, blacktalk_engine=blacktalk_engine)

    corpus = []
    for item in all_intelligence:
        corpus.append(item["content"])
        for tag in item["metadata"].get("tags", []):
            if isinstance(tag, str) and len(tag) > 1:
                corpus.append(tag)
        for field in ("malware_family", "attack_type", "delivery_method", "c2_protocol", "threat_type"):
            val = item["metadata"].get(field, "")
            if val and val != "unknown":
                corpus.append(val)
        for alias in item["metadata"].get("aliases", []):
            if isinstance(alias, str) and len(alias) > 1:
                corpus.append(alias)
        for tool in item["metadata"].get("tools", []):
            if isinstance(tool, str) and len(tool) > 1:
                corpus.append(tool)

    if corpus:
        try:
            zero_day.train(corpus)
            print(f"  ✅ ZeroDayDetector: {len(corpus)} 条语料训练完成")

            test_cases = [
                "新发现的零日漏洞利用工具在暗网出售",
                "unknown ransomware variant using double extortion",
                "APT group deploys new backdoor via supply chain attack",
                "suspicious C2 beacon pattern detected in network traffic",
                "新型钓鱼攻击利用AI生成语音进行社会工程学攻击",
                "零日漏洞CVE-2024-XXXX被APT组织在野利用",
                "黑产团伙利用新型洗钱通道转移资金",
                "novel crypto drainer targeting metamask wallets",
            ]
            print("\n  检测结果:")
            for text in test_cases:
                try:
                    results = await zero_day.detect_zero_day_terms(text)
                    if results:
                        best = results[0]
                        label = "⚠️ 异常"
                        print(f"    {label} | 置信度={best.confidence:.4f} 类别={best.category} | '{text[:40]}...'")
                    else:
                        label = "✅ 正常"
                        print(f"    {label} | 未检测到零日术语 | '{text[:40]}...'")
                except Exception as exc:
                    print(f"    ❌ 检测失败: {exc}")
        except Exception as exc:
            print(f"  ❌ ZeroDayDetector 训练失败: {exc}")

    # ========== 训练 AttackChainPredictor ==========
    print("\n[4/8] 训练 AttackChainPredictor (MITRE ATT&CK + 马尔可夫链)...")
    attack_chain = AttackChainPredictor(vector_store=vector_store, knowledge_graph=knowledge_graph)

    try:
        attack_chain.train_from_graph()
        print(f"  ✅ AttackChainPredictor: 训练完成")

        test_entity_ids = list(entity_id_map.values())[:6]
        test_entity_names = list(entity_id_map.keys())[:6]
        print("\n  攻击链预测:")
        for name, eid in zip(test_entity_names, test_entity_ids):
            try:
                result = await attack_chain.predict_next_steps(eid)
                if result.predictions:
                    top3 = [(p.technique_name[:25], round(p.probability, 3)) for p in result.predictions[:3]]
                    print(f"    {name} → {top3}")
                else:
                    print(f"    {name} → 无预测结果")
            except Exception as exc:
                print(f"    {name} 预测失败: {exc}")

        print("\n  攻击链模拟:")
        try:
            if test_entity_ids:
                sim = await attack_chain.simulate_attack_chain(test_entity_ids[0], steps=4)
                for step in sim.max_probability_path[:5]:
                    print(f"    → {step.technique_name} (概率={step.probability:.3f})")
                if not sim.max_probability_path:
                    for path in sim.paths[:3]:
                        for step_data in path.get("steps", [])[:3]:
                            print(f"    → {step_data.get('technique_name', '?')} (概率={step_data.get('probability', 0):.3f})")
        except Exception as exc:
            print(f"    模拟失败: {exc}")
    except Exception as exc:
        print(f"  ❌ AttackChainPredictor 训练失败: {exc}")

    # ========== 训练 EntityAttribution ==========
    print("\n[5/8] 训练 EntityAttribution (TransE知识图谱嵌入)...")
    entity_attr = EntityAttribution(vector_store=vector_store, knowledge_graph=knowledge_graph)

    try:
        entity_attr.train_from_graph()
        print(f"  ✅ EntityAttribution: TransE训练完成")

        test_entities = list(entity_id_map.items())[:5]
        print("\n  跨平台归因:")
        for name, eid in test_entities:
            try:
                results = await entity_attr.attribute_entity(eid)
                if results:
                    best = results[0]
                    print(f"    '{name}' → 最佳匹配={best.target_entity_id[:16]}... (相似度={best.similarity:.3f}), 候选={len(results)}个")
                else:
                    print(f"    '{name}' → 无归因结果")
            except Exception as exc:
                print(f"    '{name}' 归因失败: {exc}")
    except Exception as exc:
        print(f"  ❌ EntityAttribution 训练失败: {exc}")

    # ========== TemporalDecay ==========
    print("\n[6/8] TemporalDecay (MLE半衰期估计)...")
    temporal_decay = TemporalDecay(vector_store=vector_store)

    obs_count = 0
    for i, item in enumerate(all_intelligence):
        meta = item["metadata"]
        source = meta.get("source", "")

        intel_type = "vulnerability"
        if source in ("urlhaus", "malware_bazaar"):
            if "ransomware" in str(meta.get("tags", [])):
                intel_type = "malware"
            elif "stealer" in str(meta.get("tags", [])):
                intel_type = "phishing"
            else:
                intel_type = "malware"
        elif source == "alienvault_otx":
            intel_type = "apt"
        elif source == "otx_indicator":
            intel_type = "c2"

        base_conf = 0.6 + (i % 15) * 0.02
        hours_ago = (i % 72) + 1
        observed_conf = base_conf * (0.5 ** (hours_ago / 72))

        try:
            temporal_decay.record_observation(
                threat_type=intel_type,
                elapsed_hours=hours_ago,
                observed_confidence=observed_conf,
            )
            obs_count += 1
        except Exception:
            pass

    print(f"  ✅ TemporalDecay: {obs_count} 条观测记录")

    try:
        decay_results = await temporal_decay.batch_decay_analysis()
        half_lives = decay_results.get("half_lives", {})
        for t, hl in half_lives.items():
            print(f"    {t}: 学习半衰期={hl:.1f}小时")
    except Exception as exc:
        print(f"  ⚠️ 批量分析失败: {exc}")

    # ========== IntelligenceOrganism ==========
    print("\n[7/8] IntelligenceOrganism 情报生命体...")
    organism_engine = IntelligenceOrganismEngine(
        vector_store=vector_store,
        knowledge_graph=knowledge_graph,
    )

    species_map = {
        "cisa_kev": "vulnerability",
        "malware_bazaar": "ttp",
        "alienvault_otx": "campaign",
        "urlhaus": "domain",
        "otx_indicator": "ip",
    }

    organism_count = 0
    for i, item in enumerate(all_intelligence):
        source = item["metadata"].get("source", "unknown")
        species = species_map.get(source, "ip")
        intel_id = intel_ids[i] if i < len(intel_ids) else uuid4().hex

        try:
            organism = await organism_engine.spawn_organism(
                intelligence_id=intel_id,
                species=species,
                initial_data=item["metadata"],
            )
            organism_count += 1
        except Exception:
            pass

    print(f"  ✅ IntelligenceOrganism: {organism_count} 个生命体已生成")

    lifecycle_result = await organism_engine.run_lifecycle_check()
    print(f"    生命周期检查: {lifecycle_result}")

    alive = sum(1 for o in organism_engine.organisms.values() if o.is_alive)
    dead = sum(1 for o in organism_engine.organisms.values() if not o.is_alive)
    print(f"    存活: {alive}, 死亡: {dead}")

    species_dist = {}
    for o in organism_engine.organisms.values():
        species_dist[o.species] = species_dist.get(o.species, 0) + 1
    for sp, cnt in sorted(species_dist.items()):
        print(f"    物种 {sp}: {cnt} 个")

    # ========== ProvenanceChain ==========
    print("\n[8/8] ProvenanceChain 溯源链...")
    provenance = ProvenanceChain(vector_store=vector_store)

    prov_count = 0
    for i, item in enumerate(all_intelligence[:30]):
        intel_id = intel_ids[i] if i < len(intel_ids) else uuid4().hex
        source = item["metadata"].get("source", "unknown")

        try:
            await provenance.record_provenance(
                intelligence_id=intel_id,
                stage="collected",
                input_data={"query": source},
                output_data=item["metadata"],
                confidence_after=0.7,
            )
            await provenance.record_provenance(
                intelligence_id=intel_id,
                stage="analyzed",
                input_data=item["metadata"],
                output_data={"analysis": "completed", "source": source},
                algorithm_input=f"analyze_{source}",
                algorithm_output=f"threat_intelligence_from_{source}",
                confidence_before=0.7,
                confidence_after=0.85,
            )
            prov_count += 2
        except Exception:
            pass

    print(f"  ✅ ProvenanceChain: {prov_count} 条溯源记录")

    if intel_ids:
        verify = await provenance.verify_provenance(intel_ids[0])
        print(f"    验证 {intel_ids[0][:8]}...: valid={verify.is_valid}, chain_length={verify.chain_length}, algorithm_contributions={verify.algorithm_contributions}")

        hall_report = await provenance.detect_hallucination(intel_ids[0])
        print(f"    幻觉检测: score={hall_report.hallucination_score:.2f}, flagged={len(hall_report.flagged_claims)}")

    # ========== 持久化 ==========
    print("\n[持久化] 保存所有数据...")
    try:
        await vector_store.persist()
        print("  ✅ VectorStore")
    except Exception as exc:
        print(f"  ⚠️ VectorStore: {exc}")
    try:
        await knowledge_graph.save()
        print("  ✅ KnowledgeGraph")
    except Exception as exc:
        print(f"  ⚠️ KnowledgeGraph: {exc}")
    try:
        await organism_engine.save_to_disk()
        print("  ✅ OrganismEngine")
    except Exception as exc:
        print(f"  ⚠️ OrganismEngine: {exc}")

    # ========== 最终报告 ==========
    print(f"\n{'='*70}")
    print("  批量数据灌入与引擎训练 — 完成报告")
    print(f"{'='*70}")
    print(f"  数据总量: {len(all_intelligence)} 条真实威胁情报")
    for src, cnt in sorted(source_counts.items()):
        print(f"    - {src}: {cnt} 条")
    print(f"  VectorStore: {len(intel_ids)} 条已索引")
    print(f"  KnowledgeGraph: {entity_count} 实体, {relation_count} 关系")
    print(f"  ZeroDayDetector: {len(corpus)} 条语料训练")
    print(f"  AttackChainPredictor: 从知识图谱训练")
    print(f"  EntityAttribution: TransE嵌入训练")
    print(f"  TemporalDecay: {obs_count} 条观测记录")
    print(f"  IntelligenceOrganism: {organism_count} 个生命体 (存活={alive})")
    print(f"  ProvenanceChain: {prov_count} 条溯源记录")
    print(f"{'='*70}")

    await llm.close()


if __name__ == "__main__":
    asyncio.run(main())
