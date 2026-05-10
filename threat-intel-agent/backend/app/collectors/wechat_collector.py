import aiohttp
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.llm import LLMService
from app.config import settings


class WeChatCollector:
    SOGOU_WECHAT = "https://weixin.sogou.com/weixin"
    SOGOU_ARTICLE = "https://weixin.sogou.com/article"

    def __init__(self, llm: LLMService):
        self.llm = llm
        self.logger = logger.bind(collector="wechat")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
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
        self.logger.info(f"Collecting from WeChat: keywords={keywords}, max_results={max_results}")

        items = await self._collect_sogou(keywords, max_results)
        if items:
            return items

        self.logger.warning("Sogou WeChat search failed, falling back to LLM analysis")
        return await self._llm_analyze(keywords, max_results)

    async def _collect_sogou(self, keywords: List[str], max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []

        try:
            search_kw = " ".join(keywords) if keywords else "黑灰产 反诈"
            async with session.get(
                self.SOGOU_WECHAT,
                params={"type": "2", "query": search_kw, "s_from": "input"},
            ) as resp:
                if resp.status != 200:
                    self.logger.warning(f"Sogou WeChat returned {resp.status}")
                    return items

                text = await resp.text()
                import re
                title_pattern = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', re.IGNORECASE)
                matches = title_pattern.findall(text)

                for href, title in matches[:max_results]:
                    title = title.strip()
                    if not title or len(title) < 4:
                        continue

                    clean_title = re.sub(r'<[^>]+>', '', title)
                    if any(skip in clean_title for skip in ['登录', '注册', '搜狗', '微信']):
                        continue

                    items.append({
                        "content": f"[微信公众号] {clean_title}",
                        "source_url": href if href.startswith("http") else f"https://weixin.sogou.com{href}",
                        "metadata": {
                            "source": "sogou_wechat",
                            "title": clean_title,
                            "search_keyword": search_kw,
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        },
                    })
        except Exception as exc:
            self.logger.warning(f"Sogou WeChat collection failed: {exc}")

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
        prompt = f"关键词：{keyword_str}\n请基于这些关键词分析可能的微信/社交媒体黑灰产威胁情报。"

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
            self.logger.error(f"WeChat LLM analysis failed: {exc}")
            return []
