from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from loguru import logger

from app.agents.base import BaseAgent
from app.core.blacktalk_engine import BlackTalkEngine
from app.core.llm import LLMService
from app.core.vector_store import VectorStore
from app.models.intelligence import (
    CleanedIntelligence,
    ThreatLevel,
)


class CleanerAgent(BaseAgent):
    def __init__(
        self,
        llm: LLMService,
        vector_store: VectorStore,
        blacktalk_engine: BlackTalkEngine,
    ):
        super().__init__("cleaner", llm, vector_store)
        self.blacktalk_engine = blacktalk_engine

    async def execute(self, task: Dict) -> Dict:
        task_type = task.get("type", "clean")
        try:
            if task_type == "clean":
                raw_intel = task.get("raw_intelligence")
                if not raw_intel:
                    return self._create_task_result(
                        status="failed",
                        data={},
                        errors=["raw_intelligence is required for clean task"],
                    )
                decode_blacktalk = task.get("decode_blacktalk", True)
                extract_entities = task.get("extract_entities", True)
                cleaned = await self.clean(
                    raw_intel,
                    decode_blacktalk=decode_blacktalk,
                    extract_entities=extract_entities,
                )
                result = self._create_task_result(
                    status="success",
                    data={"cleaned_intelligence": cleaned},
                )

            elif task_type == "batch_clean":
                raw_intels = task.get("raw_intelligence", [])
                if not raw_intels:
                    return self._create_task_result(
                        status="failed",
                        data={},
                        errors=["raw_intelligence list is required for batch_clean"],
                    )
                decode_blacktalk = task.get("decode_blacktalk", True)
                extract_entities = task.get("extract_entities", True)
                cleaned_list = await self.batch_clean(
                    raw_intels,
                    decode_blacktalk=decode_blacktalk,
                    extract_entities=extract_entities,
                )
                result = self._create_task_result(
                    status="success",
                    data={
                        "total_input": len(raw_intels),
                        "total_cleaned": len(cleaned_list),
                        "cleaned_intelligences": cleaned_list,
                    },
                )

            else:
                result = self._create_task_result(
                    status="failed",
                    data={},
                    errors=[f"Unknown task type: {task_type}"],
                )

        except Exception as exc:
            self.logger.error(f"Cleaner task failed: {exc}")
            result = self._create_task_result(
                status="failed",
                data={},
                errors=[str(exc)],
            )

        await self._log_execution(task, result)
        return result

    async def clean(
        self,
        raw_intel: Dict,
        decode_blacktalk: bool = True,
        extract_entities: bool = True,
    ) -> Dict:
        content = raw_intel.get("content", "")
        raw_id = raw_intel.get("id", uuid4().hex)

        if not content:
            cleaned = CleanedIntelligence(
                raw_id=raw_id,
                content="",
                threat_level=ThreatLevel.INFO,
            )
            return cleaned.model_dump()

        cleaned_content = await self.remove_noise(content)

        decoded_content = cleaned_content
        blacktalk_terms: Dict[str, str] = {}
        if decode_blacktalk:
            decoded_content, blacktalk_terms = await self.blacktalk_engine.decode(
                cleaned_content
            )
            if blacktalk_terms:
                try:
                    await self.blacktalk_engine.auto_learn(
                        text=content,
                        decoded_terms=blacktalk_terms,
                    )
                except Exception as exc:
                    self.logger.warning(
                        f"Auto-learn blacktalk failed: {exc}"
                    )

        entities: List[str] = []
        entity_details: List[Dict] = []
        if extract_entities:
            entity_details = await self.extract_entities(decoded_content)
            entities = [e["value"] for e in entity_details]

        threat_level = await self.assess_threat_level(
            decoded_content, blacktalk_terms
        )

        cleaned = CleanedIntelligence(
            raw_id=raw_id,
            content=cleaned_content,
            decoded_content=decoded_content if blacktalk_terms else None,
            blacktalk_terms=blacktalk_terms,
            entities=entities,
            threat_level=threat_level,
        )

        try:
            await self.vector_store.add_intelligence(
                intel_id=cleaned.id,
                content=decoded_content,
                metadata={
                    "raw_id": raw_id,
                    "status": "cleaned",
                    "threat_level": threat_level,
                    "blacktalk_count": len(blacktalk_terms),
                    "entity_count": len(entities),
                    "cleaned_at": cleaned.cleaned_at.isoformat(),
                },
            )
        except Exception as exc:
            self.logger.warning(
                f"Failed to store cleaned intelligence: {exc}"
            )

        result = cleaned.model_dump()
        result["entity_details"] = entity_details
        return result

    async def batch_clean(
        self,
        raw_intels: List[Dict],
        decode_blacktalk: bool = True,
        extract_entities: bool = True,
    ) -> List[Dict]:
        seen_contents: set = set()
        unique_intels: List[Dict] = []

        for intel in raw_intels:
            content = intel.get("content", "")
            if not content:
                continue
            content_key = content.strip().lower()[:200]
            if content_key in seen_contents:
                continue
            seen_contents.add(content_key)
            unique_intels.append(intel)

        self.logger.info(
            f"Batch dedup: {len(raw_intels)} -> {len(unique_intels)} items"
        )

        cleaned_list: List[Dict] = []
        for intel in unique_intels:
            try:
                cleaned = await self.clean(
                    raw_intel=intel,
                    decode_blacktalk=decode_blacktalk,
                    extract_entities=extract_entities,
                )
                cleaned_list.append(cleaned)
            except Exception as exc:
                self.logger.error(
                    f"Failed to clean item {intel.get('id', 'unknown')}: {exc}"
                )
                continue

        self.logger.info(
            f"Batch clean completed: {len(cleaned_list)}/{len(unique_intels)} items cleaned"
        )
        return cleaned_list

    async def remove_noise(self, content: str) -> str:
        if not content or len(content.strip()) < 10:
            return content

        system_prompt = (
            "你是一个黑灰产情报清洗专家。请对以下原始情报内容进行去噪处理，"
            "去除以下内容：\n"
            "1. 广告信息（如推广链接、微信号推广等与核心情报无关的内容）\n"
            "2. 多余的表情符号和格式化残留\n"
            "3. 与核心主题无关的闲聊内容\n"
            "4. 重复啰嗦的表述\n\n"
            "要求：\n"
            "- 保留所有与黑灰产相关的核心信息\n"
            "- 保留黑话/暗语原样，不要翻译或替换\n"
            "- 保留IP、域名、URL、手机号等关键实体\n"
            "- 保持原文语义不变\n"
            "- 只返回清洗后的文本，不要添加任何解释"
        )
        prompt = f"请清洗以下原始情报内容：\n\n{content}"

        try:
            cleaned = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=2048,
            )
            cleaned = cleaned.strip()
            if len(cleaned) < len(content) * 0.3:
                self.logger.warning(
                    "Cleaned content too short, using original"
                )
                return content
            return cleaned
        except Exception as exc:
            self.logger.warning(f"Noise removal failed, using original: {exc}")
            return content

    async def extract_entities(self, content: str) -> List[Dict]:
        if not content:
            return []

        system_prompt = (
            "你是一个黑灰产情报实体提取专家。从以下文本中提取所有有价值的实体信息。\n\n"
            "需要提取的实体类型：\n"
            "- ip: IP地址\n"
            "- domain: 域名\n"
            "- url: URL链接\n"
            "- phone: 手机号码\n"
            "- email: 邮箱地址\n"
            "- crypto_wallet: 加密货币钱包地址\n"
            "- account: 账号名称（QQ号、微信号、Telegram用户名等）\n"
            "- tool: 工具名称（木马、软件、平台名称等）\n"
            "- organization: 组织/团伙名称\n"
            "- person: 人名或代号\n"
            "- payment_method: 支付方式（银行卡号、支付宝、微信支付等）\n\n"
            "返回JSON数组，每个元素包含：\n"
            "- type: 实体类型（上述之一）\n"
            "- value: 实体值\n"
            "- context: 实体出现的上下文（原文中包含该实体的短句）\n\n"
            "只返回JSON数组，不要其他内容。如果没有实体，返回空数组[]。"
        )
        prompt = f"请从以下文本中提取实体：\n\n{content}"

        try:
            result = await self.llm.generate_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
            )
            if isinstance(result, list):
                valid_entities = []
                for item in result:
                    if isinstance(item, dict) and "type" in item and "value" in item:
                        valid_entities.append({
                            "type": item["type"],
                            "value": item["value"],
                            "context": item.get("context", ""),
                        })
                return valid_entities
            if isinstance(result, dict):
                if "entities" in result and isinstance(result["entities"], list):
                    return [
                        {
                            "type": e.get("type", "unknown"),
                            "value": e.get("value", ""),
                            "context": e.get("context", ""),
                        }
                        for e in result["entities"]
                        if isinstance(e, dict) and e.get("value")
                    ]
            return []
        except Exception as exc:
            self.logger.warning(f"Entity extraction failed: {exc}")
            return []

    async def assess_threat_level(
        self, content: str, decoded_terms: Dict[str, str]
    ) -> str:
        blacktalk_density = 0.0
        if content and decoded_terms:
            total_terms = sum(
                content.count(term) for term in decoded_terms.keys()
            )
            content_len = max(len(content), 1)
            blacktalk_density = min(total_terms / (content_len / 50.0), 1.0)

        system_prompt = (
            "你是一个黑灰产威胁等级评估专家。根据以下情报内容和黑话解码信息，"
            "评估该情报的威胁等级。\n\n"
            "威胁等级定义：\n"
            "- critical: 涉及正在进行的重大犯罪活动、大规模数据泄露、关键基础设施攻击\n"
            "- high: 涉及具体的犯罪工具/方法、明确的攻击计划、大量个人信息交易\n"
            "- medium: 涉及可疑活动但缺乏具体细节、一般性的黑产讨论\n"
            "- low: 间接提及黑产活动、信息较为模糊\n"
            "- info: 仅为信息性内容，无直接威胁\n\n"
            "只返回威胁等级（critical/high/medium/low/info），不要其他内容。"
        )
        decoded_str = ""
        if decoded_terms:
            decoded_str = "黑话解码：" + "、".join(
                f"{k}({v})" for k, v in decoded_terms.items()
            )
        prompt = (
            f"情报内容：{content}\n\n"
            f"{decoded_str}\n\n"
            f"黑话密度：{blacktalk_density:.2f}\n\n"
            f"请评估威胁等级。"
        )

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=20,
            )
            level_str = response.strip().lower()
            valid_levels = {"critical", "high", "medium", "low", "info"}
            if level_str in valid_levels:
                return level_str
        except Exception as exc:
            self.logger.warning(f"Threat level assessment failed: {exc}")

        if blacktalk_density > 0.5:
            return "high"
        if blacktalk_density > 0.2:
            return "medium"
        if decoded_terms:
            return "low"
        return "info"
