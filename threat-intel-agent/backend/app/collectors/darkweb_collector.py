import aiohttp
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.config import settings


class DarkWebCollector:
    URLHAUS_API = "https://urlhaus-api.abuse.ch/v1/urls/recent/"
    ABUSE_CH_MALWARE_BAZAAR = "https://mb-api.abuse.ch/api/v1/"

    def __init__(self):
        self.logger = logger.bind(collector="darkweb")
        self._session: Optional[aiohttp.ClientSession] = None

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
        self.logger.info(f"Collecting from DarkWeb/ThreatFeeds: keywords={keywords}, max_results={max_results}")

        items: List[Dict] = []

        try:
            urlhaus_items = await self._collect_urlhaus(max_results)
            items.extend(urlhaus_items)
        except Exception as exc:
            self.logger.warning(f"URLhaus failed: {exc}")

        if len(items) < max_results:
            try:
                malware_items = await self._collect_malware_bazaar(max_results - len(items))
                items.extend(malware_items)
            except Exception as exc:
                self.logger.warning(f"MalwareBazaar failed: {exc}")

        if items:
            self.logger.info(f"Collected {len(items)} real items from dark web/threat feeds")
        else:
            self.logger.error(
                "All dark web/threat feed sources failed. "
                "URLhaus and MalwareBazaar are free APIs that should work without authentication. "
                "Check network connectivity."
            )

        return items[:max_results]

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

    async def _collect_malware_bazaar(self, max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            payload = {"query": "get_recent", "selector": "time"}
            async with session.post(self.ABUSE_CH_MALWARE_BAZAAR, data=payload) as resp:
                if resp.status != 200:
                    self.logger.warning(f"MalwareBazaar returned {resp.status}")
                    return items
                data = await resp.json(content_type=None)
                for entry in data.get("data", [])[:max_results]:
                    sha256 = entry.get("sha256_hash", "")
                    malware_name = entry.get("malware", "")
                    family = entry.get("family", "")
                    tags = entry.get("tags", [])
                    delivery_method = entry.get("delivery_method", "")
                    first_seen = entry.get("first_seen_utc", "")

                    content = f"[MalwareBazaar] 恶意软件样本: {malware_name}"
                    if family:
                        content += f" | 家族: {family}"
                    if delivery_method:
                        content += f" | 传播方式: {delivery_method}"
                    if tags:
                        content += f" | 标签: {','.join(str(t) for t in tags[:5])}"

                    items.append({
                        "content": content,
                        "source_url": f"https://bazaar.abuse.ch/sample/{sha256}/" if sha256 else "",
                        "metadata": {
                            "source": "malware_bazaar",
                            "sha256": sha256,
                            "malware_name": malware_name,
                            "family": family,
                            "delivery_method": delivery_method,
                            "tags": tags[:10] if tags else [],
                            "first_seen": first_seen,
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        },
                    })
        except Exception as exc:
            self.logger.warning(f"MalwareBazaar collection failed: {exc}")

        return items
