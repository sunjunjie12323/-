import aiohttp
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.llm import LLMService
from app.config import settings


class DarkWebCollector:
    URLHAUS_API = "https://urlhaus-api.abuse.ch/v1/urls/recent/"
    ABUSEIPDB_API = "https://api.abuseipdb.com/api/v2/check"
    HIBP_API = "https://haveibeenpwned.com/api/v3/breaches"

    def __init__(self, llm: LLMService):
        self.llm = llm
        self.logger = logger.bind(collector="darkweb")
        self._session: Optional[aiohttp.ClientSession] = None
        self._abuseipdb_key = settings.ABUSEIPDB_API_KEY

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {"User-Agent": "ThreatIntelAgent/1.0"}
            if self._abuseipdb_key:
                headers["Key"] = self._abuseipdb_key
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
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
        self.logger.info(f"Collecting from DarkWeb/ThreatFeeds: keywords={keywords}, max_results={max_results}")

        items: List[Dict] = []

        try:
            urlhaus_items = await self._collect_urlhaus(max_results)
            items.extend(urlhaus_items)
        except Exception as exc:
            self.logger.warning(f"URLhaus failed: {exc}")

        if len(items) < max_results:
            try:
                hibp_items = await self._collect_hibp(max_results - len(items))
                items.extend(hibp_items)
            except Exception as exc:
                self.logger.warning(f"HIBP failed: {exc}")

        if items:
            self.logger.info(f"Collected {len(items)} items from real dark web/threat feeds")
            return items[:max_results]

        self.logger.warning("All real dark web/threat feeds failed, falling back to LLM analysis")
        return await self._llm_analyze(keywords, max_results)

    async def _collect_urlhaus(self, max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            async with session.post(self.URLHAUS_API) as resp:
                if resp.status != 200:
                    self.logger.warning(f"URLhaus returned {resp.status}")
                    return items
                data = await resp.json(content_type=None)
                for entry in data.get("urls", [])[:max_results]:
                    threat = entry.get("threat", "unknown")
                    url = entry.get("url", "")
                    host = entry.get("host", "")
                    tags = entry.get("tags", [])

                    content = f"[URLhaus] 恶意URL: {url}"
                    if threat:
                        content += f" | 威胁: {threat}"
                    if host:
                        content += f" | 主机: {host}"
                    if tags:
                        content += f" | 标签: {','.join(str(t) for t in tags)}"

                    items.append({
                        "content": content,
                        "source_url": entry.get("urlhaus_reference", ""),
                        "metadata": {
                            "source": "urlhaus",
                            "threat_type": threat,
                            "url": url,
                            "host": host,
                            "tags": tags,
                            "reporter": entry.get("reporter", ""),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        },
                    })
        except Exception as exc:
            self.logger.warning(f"URLhaus collection failed: {exc}")

        return items

    async def _collect_hibp(self, max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            headers = {
                "User-Agent": "ThreatIntelAgent/1.0",
                "hibp-api-key": settings.VIRUSTOTAL_API_KEY or "",
            }
            async with session.get(self.HIBP_API, headers=headers) as resp:
                if resp.status != 200:
                    self.logger.warning(f"HIBP returned {resp.status}")
                    return items
                data = await resp.json(content_type=None)
                if not isinstance(data, list):
                    return items

                for breach in data[:max_results]:
                    name = breach.get("Name", "")
                    domain = breach.get("Domain", "")
                    breach_date = breach.get("BreachDate", "")
                    pwn_count = breach.get("PwnCount", 0)
                    description = breach.get("Description", "")[:200]

                    content = f"[HIBP] 数据泄露: {name}"
                    if domain:
                        content += f" | 域名: {domain}"
                    if breach_date:
                        content += f" | 日期: {breach_date}"
                    content += f" | 影响人数: {pwn_count}"

                    items.append({
                        "content": content,
                        "source_url": f"https://haveibeenpwned.com/PwnedWebsites#{name}",
                        "metadata": {
                            "source": "hibp",
                            "breach_name": name,
                            "domain": domain,
                            "breach_date": breach_date,
                            "pwn_count": pwn_count,
                            "description": description,
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        },
                    })
        except Exception as exc:
            self.logger.warning(f"HIBP collection failed: {exc}")

        return items

    async def _llm_analyze(self, keywords: List[str], max_results: int) -> List[Dict]:
        system_prompt = (
            "你是一个黑灰产情报分析专家。基于给定的关键词，分析当前可能存在的暗网/深网黑灰产威胁趋势。\n\n"
            "返回JSON数组，每个元素包含：\n"
            "- content: 基于关键词推断的可能威胁情报内容\n"
            "- source_url: 留空字符串\n"
            "- metadata: 元数据对象，必须包含source='llm_analysis'、analysis_type='keyword_inference'、collected_at等字段\n\n"
            "生成2-5条分析结果。只返回JSON数组。"
        )
        keyword_str = "、".join(keywords) if keywords else "黑灰产"
        prompt = f"关键词：{keyword_str}\n请基于这些关键词分析可能的暗网/深网黑灰产威胁情报。"

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
                        item.setdefault("source_url", "")
                        item.setdefault("metadata", {
                            "source": "llm_analysis",
                            "analysis_type": "keyword_inference",
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        })
                        items.append(item)
            elif isinstance(result, dict):
                result.setdefault("source_url", "")
                result.setdefault("metadata", {
                    "source": "llm_analysis",
                    "analysis_type": "keyword_inference",
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                })
                items.append(result)
            return items
        except Exception as exc:
            self.logger.error(f"DarkWeb LLM analysis failed: {exc}")
            return []
