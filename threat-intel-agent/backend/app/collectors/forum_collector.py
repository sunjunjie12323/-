import aiohttp
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.llm import LLMService
from app.config import settings


class ForumCollector:
    OTX_API_BASE = "https://otx.alienvault.com/api/v1"
    PHISHTANK_API = "https://data.phishtank.com/data/online-valid.json"

    def __init__(self, llm: LLMService):
        self.llm = llm
        self.logger = logger.bind(collector="forum")
        self._session: Optional[aiohttp.ClientSession] = None
        self._otx_key = settings.ALIENVAULT_OTX_KEY

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {"User-Agent": "ThreatIntelAgent/1.0"}
            if self._otx_key:
                headers["X-OTX-API-KEY"] = self._otx_key
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
        self.logger.info(f"Collecting from Forums/ThreatFeeds: keywords={keywords}, max_results={max_results}")

        items: List[Dict] = []

        try:
            otx_items = await self._collect_otx(keywords, max_results)
            items.extend(otx_items)
        except Exception as exc:
            self.logger.warning(f"AlienVault OTX failed: {exc}")

        if len(items) < max_results:
            try:
                phish_items = await self._collect_phishtank(max_results - len(items))
                items.extend(phish_items)
            except Exception as exc:
                self.logger.warning(f"PhishTank failed: {exc}")

        if items:
            self.logger.info(f"Collected {len(items)} items from real threat feeds")
            return items[:max_results]

        self.logger.warning("All real forum/threat feeds failed, falling back to LLM analysis")
        return await self._llm_analyze(keywords, max_results)

    async def _collect_otx(self, keywords: List[str], max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            if keywords:
                for kw in keywords[:3]:
                    url = f"{self.OTX_API_BASE}/pulses/search"
                    async with session.get(url, params={"q": kw, "limit": 20}) as resp:
                        if resp.status != 200:
                            self.logger.warning(f"OTX search returned {resp.status} for '{kw}'")
                            continue
                        data = await resp.json(content_type=None)
                        for pulse in data.get("results", []):
                            name = pulse.get("name", "")
                            description = pulse.get("description", "")[:300] if pulse.get("description") else ""
                            author = pulse.get("author", {}).get("username", "")
                            tags = pulse.get("tags", [])
                            indicators = pulse.get("indicators", [])

                            content = f"[OTX] {name}"
                            if description:
                                content += f" | {description[:150]}"
                            if tags:
                                content += f" | Tags: {','.join(str(t) for t in tags[:5])}"

                            items.append({
                                "content": content,
                                "source_url": pulse.get("url", ""),
                                "metadata": {
                                    "source": "alienvault_otx",
                                    "pulse_name": name,
                                    "author": author,
                                    "tags": tags[:10],
                                    "ioc_count": len(indicators),
                                    "collected_at": datetime.now(timezone.utc).isoformat(),
                                },
                            })
                            if len(items) >= max_results:
                                break
            else:
                url = f"{self.OTX_API_BASE}/pulses/subscribed"
                async with session.get(url, params={"limit": max_results}) as resp:
                    if resp.status != 200:
                        self.logger.warning(f"OTX subscribed returned {resp.status}")
                        return items
                    data = await resp.json(content_type=None)
                    for pulse in data.get("results", []):
                        name = pulse.get("name", "")
                        description = pulse.get("description", "")[:300] if pulse.get("description") else ""
                        items.append({
                            "content": f"[OTX] {name} | {description[:150]}",
                            "source_url": pulse.get("url", ""),
                            "metadata": {
                                "source": "alienvault_otx",
                                "pulse_name": name,
                                "collected_at": datetime.now(timezone.utc).isoformat(),
                            },
                        })
                        if len(items) >= max_results:
                            break
        except Exception as exc:
            self.logger.warning(f"OTX collection failed: {exc}")

        return items

    async def _collect_phishtank(self, max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            async with session.get(self.PHISHTANK_API) as resp:
                if resp.status != 200:
                    self.logger.warning(f"PhishTank returned {resp.status}")
                    return items
                data = await resp.json(content_type=None)
                if not isinstance(data, list):
                    return items

                for entry in data[:max_results]:
                    url = entry.get("url", "")
                    target = entry.get("target", "")
                    phish_id = entry.get("phish_id", "")

                    content = f"[PhishTank] 钓鱼网站: {url}"
                    if target:
                        content += f" | 目标: {target}"

                    items.append({
                        "content": content,
                        "source_url": f"https://www.phishtank.com/phish_detail.php?phish_id={phish_id}",
                        "metadata": {
                            "source": "phishtank",
                            "phish_url": url,
                            "target": target,
                            "phish_id": str(phish_id),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        },
                    })
        except Exception as exc:
            self.logger.warning(f"PhishTank collection failed: {exc}")

        return items

    async def _llm_analyze(self, keywords: List[str], max_results: int) -> List[Dict]:
        system_prompt = (
            "你是一个黑灰产情报分析专家。基于给定的关键词，分析当前可能存在的黑灰产威胁趋势。\n\n"
            "返回JSON数组，每个元素包含：\n"
            "- content: 基于关键词推断的可能威胁情报内容\n"
            "- source_url: 留空字符串\n"
            "- metadata: 元数据对象，必须包含source='llm_analysis'、analysis_type='keyword_inference'、collected_at等字段\n\n"
            "生成2-5条分析结果。只返回JSON数组。"
        )
        keyword_str = "、".join(keywords) if keywords else "黑灰产"
        prompt = f"关键词：{keyword_str}\n请基于这些关键词分析可能的论坛/社区黑灰产威胁情报。"

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
            self.logger.error(f"Forum LLM analysis failed: {exc}")
            return []
