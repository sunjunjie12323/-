import aiohttp
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import settings


class CommercialCollector:
    VIRUSTOTAL_BASE = "https://www.virustotal.com/api/v3"
    THREATBOOK_BASE = "https://api.threatbook.cn/v3"
    QIANXIN_BASE = "https://ti.qianxin.com/api/v1"

    def __init__(self):
        self.logger = logger.bind(collector="commercial")
        self._session: Optional[aiohttp.ClientSession] = None

        self._vt_api_key = getattr(settings, "VIRUSTOTAL_API_KEY", "") or ""
        self._threatbook_api_key = (
            getattr(settings, "THREATBOOK_API_KEY", "") or ""
        )
        self._qianxin_api_key = (
            getattr(settings, "QIANXIN_API_KEY", "") or ""
        )

        self._sources_enabled = {
            "virustotal": bool(self._vt_api_key),
            "threatbook": bool(self._threatbook_api_key),
            "qianxin": bool(self._qianxin_api_key),
        }

        enabled = [s for s, v in self._sources_enabled.items() if v]
        if enabled:
            self.logger.info(
                f"CommercialCollector initialized with sources: {enabled}"
            )
        else:
            self.logger.info(
                "CommercialCollector initialized with no API keys configured"
            )

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "ThreatIntelAgent/1.0"},
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def collect(
        self,
        keywords: List[str],
        max_results: int = 50,
        time_range: Optional[Dict] = None,
        **kwargs: Any,
    ) -> List[Dict]:
        self.logger.info(
            f"Collecting from commercial sources: keywords={keywords}, "
            f"max_results={max_results}"
        )

        items: List[Dict] = []
        remaining = max_results

        if self._sources_enabled["virustotal"] and remaining > 0:
            try:
                vt_items = await self._collect_virustotal(
                    keywords, min(remaining, max_results)
                )
                items.extend(vt_items)
                remaining = max_results - len(items)
            except Exception as exc:
                self.logger.warning(f"VirusTotal collection failed: {exc}")

        if self._sources_enabled["threatbook"] and remaining > 0:
            try:
                tb_items = await self._collect_threatbook(
                    keywords, min(remaining, max_results)
                )
                items.extend(tb_items)
                remaining = max_results - len(items)
            except Exception as exc:
                self.logger.warning(f"ThreatBook collection failed: {exc}")

        if self._sources_enabled["qianxin"] and remaining > 0:
            try:
                qx_items = await self._collect_qianxin(
                    keywords, min(remaining, max_results)
                )
                items.extend(qx_items)
                remaining = max_results - len(items)
            except Exception as exc:
                self.logger.warning(f"Qianxin TI collection failed: {exc}")

        if not items:
            self.logger.info(
                "No results from commercial sources "
                "(APIs may be unconfigured or unreachable)"
            )

        return items[:max_results]

    async def _collect_virustotal(
        self, keywords: List[str], max_results: int
    ) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        for keyword in keywords[:3]:
            try:
                url = f"{self.VIRUSTOTAL_BASE}/search"
                params = {"query": keyword, "limit": min(max_results, 40)}
                headers = {"X-Apikey": self._vt_api_key}

                async with session.get(
                    url, params=params, headers=headers
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning(
                            f"VirusTotal returned {resp.status} for '{keyword}'"
                        )
                        continue

                    data = await resp.json(content_type=None)
                    vt_data = data.get("data", [])

                    for entry in vt_data:
                        item_type = entry.get("type", "unknown")
                        attributes = entry.get("attributes", {})
                        last_analysis = attributes.get(
                            "last_analysis_stats", {}
                        )
                        malicious = last_analysis.get("malicious", 0)
                        total = sum(last_analysis.values())
                        reputation = attributes.get("reputation", 0)

                        content_parts = [
                            f"[VirusTotal] {item_type}: {keyword}"
                        ]
                        if malicious > 0:
                            content_parts.append(
                                f"恶意检测: {malicious}/{total} 引擎"
                            )
                        if reputation != 0:
                            content_parts.append(f"信誉分: {reputation}")

                        threat_labels = attributes.get(
                            "popular_threat_classification", {}
                        )
                        suggested_label = threat_labels.get(
                            "suggested_threat_label", ""
                        )
                        if suggested_label:
                            content_parts.append(
                                f"威胁分类: {suggested_label}"
                            )

                        content = " | ".join(content_parts)

                        items.append(
                            {
                                "content": content,
                                "source_url": f"https://www.virustotal.com/gui/search/{keyword}",
                                "metadata": {
                                    "source": "virustotal",
                                    "item_type": item_type,
                                    "malicious_engines": malicious,
                                    "total_engines": total,
                                    "reputation": reputation,
                                    "suggested_threat_label": suggested_label,
                                    "collected_at": datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                                },
                            }
                        )

                        if len(items) >= max_results:
                            break

            except Exception as exc:
                self.logger.warning(
                    f"VirusTotal query failed for '{keyword}': {exc}"
                )

        if items:
            self.logger.info(f"VirusTotal: collected {len(items)} items")
        return items

    async def _collect_threatbook(
        self, keywords: List[str], max_results: int
    ) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        for keyword in keywords[:3]:
            try:
                url = f"{self.THREATBOOK_BASE}/threat_intelligence"
                params = {
                    "query": keyword,
                    "apikey": self._threatbook_api_key,
                    "limit": min(max_results, 20),
                }

                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        self.logger.warning(
                            f"ThreatBook returned {resp.status} for '{keyword}'"
                        )
                        continue

                    data = await resp.json(content_type=None)
                    response_code = data.get("response_code", -1)
                    if response_code != 0:
                        self.logger.warning(
                            f"ThreatBook API error for '{keyword}': "
                            f"code={response_code}, "
                            f"msg={data.get('verbose_msg', '')}"
                        )
                        continue

                    threat_details = data.get("data", {}).get(
                        "threat_tags", []
                    )
                    ioc_details = data.get("data", {}).get("ioc", {})

                    content_parts = [
                        f"[微步在线] 威胁情报: {keyword}"
                    ]

                    if threat_details:
                        tags = [
                            t.get("tag", "")
                            for t in threat_details[:5]
                            if t.get("tag")
                        ]
                        if tags:
                            content_parts.append(f"威胁标签: {', '.join(tags)}")

                    if ioc_details:
                        risk_level = ioc_details.get("risk_level", "")
                        if risk_level:
                            content_parts.append(f"风险等级: {risk_level}")

                        judgments = ioc_details.get("judgments", [])
                        if judgments:
                            content_parts.append(
                                f"判定: {', '.join(str(j) for j in judgments[:3])}"
                            )

                    content = " | ".join(content_parts)

                    items.append(
                        {
                            "content": content,
                            "source_url": f"https://x.threatbook.com/node/v4/object_detail/{keyword}",
                            "metadata": {
                                "source": "threatbook",
                                "keyword": keyword,
                                "threat_tags": [
                                    t.get("tag", "")
                                    for t in threat_details[:10]
                                ],
                                "risk_level": ioc_details.get(
                                    "risk_level", ""
                                ),
                                "judgments": ioc_details.get(
                                    "judgments", []
                                )[:5],
                                "collected_at": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            },
                        }
                    )

                    if len(items) >= max_results:
                        break

            except Exception as exc:
                self.logger.warning(
                    f"ThreatBook query failed for '{keyword}': {exc}"
                )

        if items:
            self.logger.info(f"ThreatBook: collected {len(items)} items")
        return items

    async def _collect_qianxin(
        self, keywords: List[str], max_results: int
    ) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        for keyword in keywords[:3]:
            try:
                url = f"{self.QIANXIN_BASE}/threat"
                params = {
                    "query": keyword,
                    "apikey": self._qianxin_api_key,
                    "limit": min(max_results, 20),
                }

                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        self.logger.warning(
                            f"Qianxin TI returned {resp.status} for '{keyword}'"
                        )
                        continue

                    data = await resp.json(content_type=None)
                    code = data.get("code", -1)
                    if code != 0:
                        self.logger.warning(
                            f"Qianxin TI API error for '{keyword}': "
                            f"code={code}, msg={data.get('msg', '')}"
                        )
                        continue

                    threat_list = data.get("data", [])
                    if isinstance(threat_list, dict):
                        threat_list = threat_list.get("list", [threat_list])

                    for entry in threat_list:
                        threat_name = entry.get("name", entry.get("title", ""))
                        threat_type = entry.get("type", "")
                        severity = entry.get("severity", entry.get("level", ""))
                        description = entry.get("description", "")
                        iocs = entry.get("iocs", {})
                        tags = entry.get("tags", [])

                        content_parts = [
                            f"[奇安信TI] 威胁情报: {keyword}"
                        ]
                        if threat_name:
                            content_parts.append(f"威胁名称: {threat_name}")
                        if threat_type:
                            content_parts.append(f"类型: {threat_type}")
                        if severity:
                            content_parts.append(f"严重程度: {severity}")
                        if tags:
                            content_parts.append(
                                f"标签: {', '.join(str(t) for t in tags[:5])}"
                            )
                        if description:
                            content_parts.append(
                                f"描述: {description[:200]}"
                            )

                        content = " | ".join(content_parts)

                        ioc_list = []
                        if isinstance(iocs, dict):
                            for ioc_type, ioc_values in iocs.items():
                                if isinstance(ioc_values, list):
                                    for v in ioc_values[:5]:
                                        ioc_list.append(
                                            f"{ioc_type}: {v}"
                                        )
                                else:
                                    ioc_list.append(
                                        f"{ioc_type}: {ioc_values}"
                                    )

                        items.append(
                            {
                                "content": content,
                                "source_url": entry.get("url", ""),
                                "metadata": {
                                    "source": "qianxin",
                                    "keyword": keyword,
                                    "threat_name": threat_name,
                                    "threat_type": threat_type,
                                    "severity": severity,
                                    "tags": tags[:10] if tags else [],
                                    "iocs": ioc_list[:20],
                                    "collected_at": datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                                },
                            }
                        )

                        if len(items) >= max_results:
                            break

            except Exception as exc:
                self.logger.warning(
                    f"Qianxin TI query failed for '{keyword}': {exc}"
                )

        if items:
            self.logger.info(f"Qianxin TI: collected {len(items)} items")
        return items

    async def test_connection(self) -> Dict[str, bool]:
        results = {}

        if self._sources_enabled["virustotal"]:
            try:
                session = await self._get_session()
                url = f"{self.VIRUSTOTAL_BASE}/search"
                params = {"query": "test", "limit": 1}
                headers = {"X-Apikey": self._vt_api_key}
                async with session.get(
                    url, params=params, headers=headers
                ) as resp:
                    results["virustotal"] = resp.status in (200, 401)
            except Exception:
                results["virustotal"] = False
        else:
            results["virustotal"] = False

        if self._sources_enabled["threatbook"]:
            try:
                session = await self._get_session()
                url = f"{self.THREATBOOK_BASE}/threat_intelligence"
                params = {
                    "query": "test",
                    "apikey": self._threatbook_api_key,
                    "limit": 1,
                }
                async with session.get(url, params=params) as resp:
                    results["threatbook"] = resp.status == 200
            except Exception:
                results["threatbook"] = False
        else:
            results["threatbook"] = False

        if self._sources_enabled["qianxin"]:
            try:
                session = await self._get_session()
                url = f"{self.QIANXIN_BASE}/threat"
                params = {
                    "query": "test",
                    "apikey": self._qianxin_api_key,
                    "limit": 1,
                }
                async with session.get(url, params=params) as resp:
                    results["qianxin"] = resp.status == 200
            except Exception:
                results["qianxin"] = False
        else:
            results["qianxin"] = False

        return results

    def get_status(self) -> Dict[str, Any]:
        return {
            "sources": self._sources_enabled,
            "configured_count": sum(
                1 for v in self._sources_enabled.values() if v
            ),
            "total_sources": 3,
        }
