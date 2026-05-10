from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.core.llm import LLMService


class TelegramCollector:
    def __init__(self, llm: LLMService):
        self.llm = llm
        self.logger = logger.bind(collector="telegram")

    async def collect(
        self,
        keywords: List[str],
        max_results: int = 50,
        time_range: Optional[Dict] = None,
        **kwargs: Any,
    ) -> List[Dict]:
        self.logger.info(
            f"Collecting from Telegram: keywords={keywords}, max_results={max_results}"
        )

        system_prompt = (
            "你是一个黑灰产情报模拟采集专家。模拟从Telegram群组/频道中采集到的黑灰产相关情报。\n\n"
            "返回JSON数组，每个元素包含：\n"
            "- content: 情报内容（包含黑话、暗语等真实特征，模拟Telegram消息风格）\n"
            "- source_url: 来源URL（模拟Telegram链接）\n"
            "- metadata: 元数据对象，包含channel_name、author、message_id等字段\n\n"
            "生成2-5条模拟情报。只返回JSON数组，不要其他内容。"
        )
        keyword_str = "、".join(keywords) if keywords else "黑灰产"
        prompt = (
            f"来源：Telegram\n"
            f"关键词：{keyword_str}\n"
            f"最多条数：{min(max_results, 5)}\n\n"
            f"请模拟从Telegram采集到的情报数据。"
        )

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
                        item.setdefault("source_url", "https://t.me/channel_unknown")
                        item.setdefault("metadata", {
                            "channel_name": "simulated_channel",
                            "author": "unknown",
                            "message_id": uuid4().hex[:8],
                            "collected_at": datetime.utcnow().isoformat(),
                        })
                        items.append(item)
            elif isinstance(result, dict):
                result.setdefault("source_url", "https://t.me/channel_unknown")
                result.setdefault("metadata", {
                    "channel_name": "simulated_channel",
                    "author": "unknown",
                    "message_id": uuid4().hex[:8],
                    "collected_at": datetime.utcnow().isoformat(),
                })
                items.append(result)
            self.logger.info(f"Collected {len(items)} items from Telegram")
            return items
        except Exception as exc:
            self.logger.error(f"Telegram collection failed: {exc}")
            return []
