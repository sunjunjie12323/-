import aiohttp
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.llm import LLMService
from app.config import settings


class TelegramCollector:
    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(self, llm: LLMService):
        self.llm = llm
        self.logger = logger.bind(collector="telegram")
        self._session: Optional[aiohttp.ClientSession] = None
        self._bot_token = settings.TELEGRAM_BOT_TOKEN

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _has_real_api(self) -> bool:
        return bool(self._bot_token and len(self._bot_token) > 10)

    async def collect(
        self,
        keywords: List[str],
        max_results: int = 50,
        time_range: Optional[Dict] = None,
        **kwargs: Any,
    ) -> List[Dict]:
        self.logger.info(f"Collecting from Telegram: keywords={keywords}, max_results={max_results}")

        if self._has_real_api():
            items = await self._collect_real(keywords, max_results)
            if items:
                return items
            self.logger.warning("Telegram Bot API returned no results, falling back to LLM analysis")

        return await self._llm_analyze(keywords, max_results)

    async def _collect_real(self, keywords: List[str], max_results: int) -> List[Dict]:
        session = await self._get_session()
        items: List[Dict] = []
        api_url = self.API_BASE.format(token=self._bot_token)

        try:
            async with session.get(f"{api_url}/getUpdates", params={"limit": 100}) as resp:
                if resp.status != 200:
                    self.logger.warning(f"Telegram API returned {resp.status}")
                    return items
                data = await resp.json(content_type=None)
                if not data.get("ok"):
                    self.logger.warning(f"Telegram API error: {data.get('description', 'unknown')}")
                    return items

                for update in data.get("result", []):
                    message = update.get("message") or update.get("channel_post")
                    if not message:
                        continue

                    text = message.get("text", "")
                    if not text:
                        continue

                    keyword_match = not keywords or any(kw.lower() in text.lower() for kw in keywords)
                    if not keyword_match:
                        continue

                    chat = message.get("chat", {})
                    from_user = message.get("from", {})
                    chat_id = chat.get("id", "")
                    chat_title = chat.get("title", chat.get("username", "unknown"))
                    msg_id = message.get("message_id", "")
                    date_ts = message.get("date", 0)

                    items.append({
                        "content": text,
                        "source_url": f"https://t.me/c/{abs(chat_id)}/{msg_id}" if chat_id else "",
                        "metadata": {
                            "source": "telegram",
                            "chat_id": str(chat_id),
                            "chat_title": chat_title,
                            "author": from_user.get("username", from_user.get("first_name", "unknown")),
                            "message_id": str(msg_id),
                            "date": datetime.fromtimestamp(date_ts, tz=timezone.utc).isoformat() if date_ts else "",
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        },
                    })

                    if len(items) >= max_results:
                        break

        except Exception as exc:
            self.logger.warning(f"Telegram real API failed: {exc}")

        return items

    async def _llm_analyze(self, keywords: List[str], max_results: int) -> List[Dict]:
        system_prompt = (
            "你是一个黑灰产情报分析专家。基于给定的关键词，分析当前可能存在的黑灰产威胁趋势。\n\n"
            "返回JSON数组，每个元素包含：\n"
            "- content: 基于关键词推断的可能威胁情报内容（包含黑话、暗语等特征）\n"
            "- source_url: 留空字符串\n"
            "- metadata: 元数据对象，必须包含source='llm_analysis'、analysis_type='keyword_inference'、collected_at等字段\n\n"
            "生成2-5条分析结果。只返回JSON数组。"
        )
        keyword_str = "、".join(keywords) if keywords else "黑灰产"
        prompt = f"关键词：{keyword_str}\n请基于这些关键词分析可能的黑灰产威胁情报。"

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
            self.logger.info(f"LLM analysis produced {len(items)} items for Telegram keywords")
            return items
        except Exception as exc:
            self.logger.error(f"Telegram LLM analysis failed: {exc}")
            return []
