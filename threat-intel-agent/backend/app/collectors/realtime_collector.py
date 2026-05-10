import aiohttp
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.core.llm import LLMService


class RealTimeCollector:
    REAL_SOURCES = {
        "urlhaus": "https://urlhaus-api.abuse.ch/v1/urlshaus/recent/",
        "threat_fox": "https://threatfox-api.abuse.ch/v1/",
        "malware_bazaar": "https://mb-api.abuse.ch/api/v1/",
    }

    def __init__(self, llm: LLMService):
        self.llm = llm
        self.logger = logger.bind(collector="realtime")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
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
        self.logger.info(f"RealTimeCollector: keywords={keywords}, max_results={max_results}")
        items: List[Dict] = []

        try:
            urlhaus_items = await self._collect_urlhaus(max_results)
            items.extend(urlhaus_items)
        except Exception as exc:
            self.logger.warning(f"URLhaus collection failed: {exc}")

        try:
            threatfox_items = await self._collect_threatfox(keywords, max_results)
            items.extend(threatfox_items)
        except Exception as exc:
            self.logger.warning(f"ThreatFox collection failed: {exc}")

        if not items:
            self.logger.info("No real data collected, falling back to LLM-simulated data")
            items = await self._llm_fallback(keywords, max_results)

        self.logger.info(f"RealTimeCollector: collected {len(items)} items total")
        return items[:max_results]

    async def _collect_urlhaus(self, max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            async with session.get("https://urlhaus-api.abuse.ch/v1/urls/recent/") as resp:
                if resp.status != 200:
                    self.logger.warning(f"URLhaus API returned {resp.status}")
                    return items
                data = await resp.json(content_type=None)
                urls = data.get("urls", [])

                for entry in urls[:max_results]:
                    threat_type = entry.get("threat", "unknown")
                    url = entry.get("url", "")
                    host = entry.get("host", "")
                    tags = entry.get("tags", [])

                    content = f"[URLhaus] 恶意URL: {url}"
                    if threat_type:
                        content += f" | 威胁类型: {threat_type}"
                    if host:
                        content += f" | 主机: {host}"
                    if tags:
                        content += f" | 标签: {','.join(tags)}"

                    items.append({
                        "content": content,
                        "source_url": entry.get("urlhaus_link", ""),
                        "metadata": {
                            "source": "urlhaus",
                            "threat_type": threat_type,
                            "url": url,
                            "host": host,
                            "tags": tags,
                            "reporter": entry.get("reporter", ""),
                            "first_seen": entry.get("firstseen", ""),
                            "collected_at": datetime.utcnow().isoformat(),
                        },
                    })
        except Exception as exc:
            self.logger.warning(f"URLhaus request failed: {exc}")

        return items

    async def _collect_threatfox(self, keywords: List[str], max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            payload = {"query": "search_ioc", "search_term": keywords[0] if keywords else "malware"}
            async with session.post("https://threatfox-api.abuse.ch/api/v1/", json=payload) as resp:
                if resp.status != 200:
                    self.logger.warning(f"ThreatFox API returned {resp.status}")
                    return items
                data = await resp.json(content_type=None)

                iocs = data.get("data", [])
                if not isinstance(iocs, list):
                    return items

                for entry in iocs[:max_results]:
                    ioc_type = entry.get("ioc_type", "unknown")
                    ioc_value = entry.get("ioc", "")
                    malware = entry.get("malware_printable", "unknown")
                    confidence = entry.get("confidence_level", 0)

                    content = f"[ThreatFox] IOC: {ioc_value}"
                    if ioc_type:
                        content += f" | 类型: {ioc_type}"
                    if malware:
                        content += f" | 恶意软件: {malware}"

                    items.append({
                        "content": content,
                        "source_url": entry.get("threatfox_link", ""),
                        "metadata": {
                            "source": "threatfox",
                            "ioc_type": ioc_type,
                            "ioc_value": ioc_value,
                            "malware": malware,
                            "confidence_level": confidence,
                            "reporter": entry.get("reporter", ""),
                            "first_seen": entry.get("first_seen_utc", ""),
                            "collected_at": datetime.utcnow().isoformat(),
                        },
                    })
        except Exception as exc:
            self.logger.warning(f"ThreatFox request failed: {exc}")

        return items

    async def _llm_fallback(self, keywords: List[str], max_results: int) -> List[Dict]:
        system_prompt = (
            "你是一个黑灰产情报采集专家。模拟从公开威胁情报源中采集到的情报。\n\n"
            "返回JSON数组，每个元素包含：\n"
            "- content: 情报内容\n"
            "- source_url: 来源URL\n"
            "- metadata: 元数据对象，包含source、collected_at等字段\n\n"
            "生成2-3条情报。只返回JSON数组。"
        )
        keyword_str = "、".join(keywords) if keywords else "黑灰产"
        prompt = f"关键词：{keyword_str}\n请生成相关威胁情报。"

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
            )
            items = []
            if isinstance(result, list):
                for item in result[:max_results]:
                    if isinstance(item, dict):
                        item.setdefault("source_url", "https://threat-intel.example/feed")
                        item.setdefault("metadata", {
                            "source": "llm_simulated",
                            "collected_at": datetime.utcnow().isoformat(),
                        })
                        items.append(item)
            return items
        except Exception as exc:
            self.logger.error(f"LLM fallback also failed: {exc}")
            return []
