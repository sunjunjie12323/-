import aiohttp
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import settings


class ForumCollector:
    OTX_API_BASE = "https://otx.alienvault.com/api/v1"
    CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    def __init__(self):
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
        self.logger.info(f"Collecting from Forum/ThreatFeeds: keywords={keywords}, max_results={max_results}")

        items: List[Dict] = []

        try:
            otx_items = await self._collect_otx(keywords, max_results)
            items.extend(otx_items)
        except Exception as exc:
            self.logger.warning(f"AlienVault OTX failed: {exc}")

        if len(items) < max_results:
            try:
                cisa_items = await self._collect_cisa_kev(max_results - len(items))
                items.extend(cisa_items)
            except Exception as exc:
                self.logger.warning(f"CISA KEV failed: {exc}")

        if items:
            self.logger.info(f"Collected {len(items)} real items from threat feeds")
        else:
            self.logger.error(
                "All threat feed sources failed. "
                "For AlienVault OTX: register at https://otx.alienvault.com and set ALIENVAULT_OTX_KEY in .env. "
                "CISA KEV should work without a key."
            )

        return items[:max_results]

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

    async def _collect_cisa_kev(self, max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            async with session.get(self.CISA_KEV_URL) as resp:
                if resp.status != 200:
                    self.logger.warning(f"CISA KEV returned {resp.status}")
                    return items
                data = await resp.json(content_type=None)
                vulns = data.get("vulnerabilities", [])

                for vuln in vulns[:max_results]:
                    cve_id = vuln.get("cveID", "")
                    product = vuln.get("product", "")
                    vuln_type = vuln.get("vulnerabilityName", "")
                    date_added = vuln.get("dateAdded", "")

                    content = f"[CISA KEV] 已知被利用漏洞: {cve_id}"
                    if vuln_type:
                        content += f" | {vuln_type}"
                    if product:
                        content += f" | 产品: {product}"

                    items.append({
                        "content": content,
                        "source_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                        "metadata": {
                            "source": "cisa_kev",
                            "cve_id": cve_id,
                            "product": product,
                            "vulnerability_name": vuln_type,
                            "date_added": date_added,
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        },
                    })
        except Exception as exc:
            self.logger.warning(f"CISA KEV collection failed: {exc}")

        return items
