import asyncio
import uuid
from datetime import datetime, timedelta
import random

from loguru import logger

from app.db.database import engine, Base, async_session_factory
from app.db.tables import (
    RawIntelligenceTable,
    CleanedIntelligenceTable,
    AnalyzedIntelligenceTable,
    PIRTable,
    PIRTaskTable,
    ReportTable,
)
from app.core.knowledge_graph import KnowledgeGraph
from app.core.blacktalk_engine import BlackTalkEngine, BlackTalkTerm
from app.core.llm import LLMService
from app.models.intelligence import IntelligenceSource, ThreatLevel, IntelligenceStatus
from app.models.entity import Entity, Relation, EntityType, RelationType
from app.models.pir import PIR, PIRStatus, PIRPriority


RAW_INTELLIGENCE_DATA = [
    {
        "source": "telegram",
        "content": "【跑分平台】日结日清，佣金5%-8%，支持支付宝微信银行卡，量大从优，TG: @paofen888",
        "metadata": {"group": "黑产交流群", "author": "跑分大佬"},
    },
    {
        "source": "telegram",
        "content": "出四件套，身份证+银行卡+手机卡+U盾，全部实名，价格私聊，量大优惠 TG: @sijiantao_shop",
        "metadata": {"group": "料子交易群", "author": "料主A"},
    },
    {
        "source": "telegram",
        "content": "猫池设备出售，32口64口128口都有，支持接码平台对接，稳定不掉线，售后保障",
        "metadata": {"group": "黑产工具群", "author": "设备王"},
    },
    {
        "source": "forum",
        "content": "求购拦截卡，需要移动联通电信各100张，要求能收到验证码，价格好说，长期合作",
        "metadata": {"forum": "暗网论坛A", "author": "匿名用户3821"},
    },
    {
        "source": "forum",
        "content": "杀猪盘项目招募：提供话术模板+人设包装+资金盘搭建，月入10万+，有经验优先",
        "metadata": {"forum": "灰产论坛B", "author": "盘总"},
    },
    {
        "source": "wechat",
        "content": "警惕新型套路贷：以低息贷款为诱饵，要求借款人提供银行卡和手机卡，随后通过猫池设备截取验证码，盗取借款人资金",
        "metadata": {"account": "安全研究", "title": "新型套路贷手法分析"},
    },
    {
        "source": "wechat",
        "content": "近期发现大量菠菜网站利用AI换脸技术进行真人认证绕过，建议加强活体检测的防伪能力",
        "metadata": {"account": "反欺诈中心", "title": "AI换脸绕过实名认证预警"},
    },
    {
        "source": "darkweb",
        "content": "Selling fresh CN fullz (name+ID+phone+bank), 5000+ records available, sample on request, payment in BTC",
        "metadata": {"market": "DarkMarket X", "vendor": "data_vendor_99"},
    },
    {
        "source": "darkweb",
        "content": "RAT malware for sale, supports Android/iOS/Windows, remote control + keylogging + screen capture, $500/license",
        "metadata": {"market": "DarkMarket X", "vendor": "malware_pro"},
    },
    {
        "source": "telegram",
        "content": "接码平台更新：新增东南亚号码，支持WhatsApp/Telegram/微信注册，0.5元/条，API接口可用",
        "metadata": {"group": "接码服务群", "author": "码商小王"},
    },
    {
        "source": "forum",
        "content": "水房通道稳定，支持大额，日处理100万+，费率3%，T+0到账，需要的私",
        "metadata": {"forum": "暗网论坛A", "author": "水房老板"},
    },
    {
        "source": "telegram",
        "content": "养号服务：提供各平台老号/白号，已实名认证，可接码，价格1-50元不等，量大优惠",
        "metadata": {"group": "账号交易群", "author": "号商张三"},
    },
    {
        "source": "wechat",
        "content": "黑SEO技术分享：利用蜘蛛池+站群快速提升排名，月入5万+，适合有基础的朋友",
        "metadata": {"account": "技术分享", "title": "黑SEO实战教程"},
    },
    {
        "source": "darkweb",
        "content": "Phishing kit for Chinese banks (ICBC/CMB/BOC), includes SMS gateway + domain + hosting, $2000/kit",
        "metadata": {"market": "DarkMarket Y", "vendor": "phish_master"},
    },
    {
        "source": "forum",
        "content": "撞库工具更新：支持多平台批量检测，速度10万/小时，准确率95%+，自带代理池管理",
        "metadata": {"forum": "灰产论坛B", "author": "工具开发者"},
    },
    {
        "source": "telegram",
        "content": "色流变现项目：日引流1000+，转化率5%，客单价200，日入1万+，提供全套话术和素材",
        "metadata": {"group": "流量变现群", "author": "流量王"},
    },
    {
        "source": "wechat",
        "content": "资金盘预警：XX国际宣称日收益3%，疑似庞氏骗局，已有大量投资者无法提现，请远离",
        "metadata": {"account": "金融防骗", "title": "XX国际资金盘预警"},
    },
    {
        "source": "darkweb",
        "content": "DDoS-for-hire service, up to 500Gbps, $100/hour, supports custom targets, 24/7 support",
        "metadata": {"market": "DarkMarket Y", "vendor": "ddos_king"},
    },
    {
        "source": "forum",
        "content": "脱库数据出售：某电商平台500万用户数据，含手机号+地址+购买记录，价格面议",
        "metadata": {"forum": "暗网论坛A", "author": "数据库管理员"},
    },
    {
        "source": "telegram",
        "content": "代购服务：可代购各类虚拟商品和充值卡，支持批量，价格优惠，长期合作优先",
        "metadata": {"group": "代购服务群", "author": "代购小哥"},
    },
    {
        "source": "wechat",
        "content": "裸条借贷受害者案例分析：犯罪分子通过借贷宝等平台，要求借款人提供裸照作为抵押，随后威胁敲诈",
        "metadata": {"account": "法律援助", "title": "裸条借贷案例警示"},
    },
    {
        "source": "forum",
        "content": "过桥资金提供：短期周转，日息0.5%，额度1-100万，当天放款，需要四件套做担保",
        "metadata": {"forum": "灰产论坛B", "author": "资金中介"},
    },
    {
        "source": "telegram",
        "content": "肉鸡出售：国内高质量肉鸡1万台，可做DDoS/挖矿/发信，稳定性好，价格0.5元/台",
        "metadata": {"group": "黑产工具群", "author": "肉鸡供应商"},
    },
    {
        "source": "darkweb",
        "content": "Custom malware development service, can bypass most AV/EDR, delivery in 7 days, price negotiable",
        "metadata": {"market": "DarkMarket X", "vendor": "cod3r"},
    },
    {
        "source": "wechat",
        "content": "近期薅羊毛黑产团伙利用AI批量注册账号，通过虚拟手机号接码，单日可薅上万元优惠",
        "metadata": {"account": "电商安全", "title": "AI薅羊毛黑产预警"},
    },
    {
        "source": "telegram",
        "content": "菠菜盘口搭建：提供全套系统+支付通道+域名+服务器，3天上线，包售后，价格2万起",
        "metadata": {"group": "菠菜交流群", "author": "盘口技术"},
    },
    {
        "source": "forum",
        "content": "套现渠道：信用卡/花呗/白条套现，费率3-5%，当天到账，大额可优惠",
        "metadata": {"forum": "灰产论坛B", "author": "套现王"},
    },
    {
        "source": "telegram",
        "content": "黑料出售：各类隐私数据，含开房记录/快递信息/学信网数据，按条计费，量大从优",
        "metadata": {"group": "料子交易群", "author": "数据贩子"},
    },
    {
        "source": "darkweb",
        "content": "Zero-day exploit for popular Chinese software, unpatched, $50000, verification available",
        "metadata": {"market": "DarkMarket X", "vendor": "0day_hunter"},
    },
    {
        "source": "wechat",
        "content": "反诈提醒：近期出现冒充公检法诈骗新变种，骗子利用AI语音克隆技术模仿亲友声音进行诈骗",
        "metadata": {"account": "反诈中心", "title": "AI语音克隆诈骗预警"},
    },
]


async def seed_database():
    logger.info("Starting database seeding...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    kg = KnowledgeGraph()
    llm = LLMService()

    async with async_session_factory() as session:
        for i, item in enumerate(RAW_INTELLIGENCE_DATA):
            raw_id = str(uuid.uuid4())
            now = datetime.utcnow() - timedelta(hours=random.randint(1, 720))
            raw = RawIntelligenceTable(
                id=raw_id,
                source=item["source"],
                source_url="",
                content=item["content"],
                raw_content=item["content"],
                collected_at=now,
                status="raw",
                metadata_json=str(item.get("metadata", {})),
            )
            session.add(raw)

            if random.random() < 0.6:
                cleaned_id = str(uuid.uuid4())
                cleaned = CleanedIntelligenceTable(
                    id=cleaned_id,
                    raw_id=raw_id,
                    content=item["content"],
                    decoded_content=item["content"],
                    blacktalk_terms_json="{}",
                    entities_json="[]",
                    threat_level=random.choice(["high", "critical", "medium"]),
                    cleaned_at=now + timedelta(minutes=random.randint(1, 60)),
                )
                session.add(cleaned)

                if random.random() < 0.4:
                    analyzed = AnalyzedIntelligenceTable(
                        id=str(uuid.uuid4()),
                        cleaned_id=cleaned_id,
                        threat_level=random.choice(["high", "critical", "medium"]),
                        threat_categories_json=str([random.choice(["fraud", "money_laundering", "hacking", "gambling"])]),
                        attack_patterns_json="[]",
                        technique_chain_json="[]",
                        confidence_score=round(random.uniform(0.6, 0.95), 2),
                        analysis_summary="",
                        evidence_refs_json="[]",
                        analyzed_at=now + timedelta(hours=random.randint(1, 24)),
                    )
                    session.add(analyzed)

        pirs_data = [
            {
                "title": "新型信贷欺诈手法监测",
                "description": "监测近期出现的信贷欺诈新型手法，包括套路贷、房贷背债等变种",
                "priority": "high",
                "keywords": ["信贷", "欺诈", "套路贷", "背债"],
                "target_sources": ["telegram", "forum", "wechat"],
            },
            {
                "title": "暗网数据泄露追踪",
                "description": "追踪暗网市场上出售的中国公民个人数据泄露事件",
                "priority": "critical",
                "keywords": ["数据泄露", "脱库", "个人信息", "fullz"],
                "target_sources": ["darkweb", "forum"],
            },
            {
                "title": "AI赋能黑产趋势分析",
                "description": "分析黑产利用AI技术（换脸、语音克隆、自动化攻击）的趋势和案例",
                "priority": "medium",
                "keywords": ["AI", "换脸", "语音克隆", "自动化"],
                "target_sources": ["telegram", "wechat", "darkweb"],
            },
        ]

        for pir_data in pirs_data:
            pir = PIRTable(
                id=str(uuid.uuid4()),
                title=pir_data["title"],
                description=pir_data["description"],
                priority=pir_data["priority"],
                status="active",
                keywords_json=str(pir_data["keywords"]),
                target_sources_json=str(pir_data["target_sources"]),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(pir)

        await session.commit()

    entities_data = [
        {"type": EntityType.ORGANIZATION, "value": "XX跑分平台", "context": "Telegram群组中发现的跑分洗钱平台", "confidence": 0.85},
        {"type": EntityType.TOOL, "value": "猫池设备", "context": "批量收发短信验证码的设备", "confidence": 0.9},
        {"type": EntityType.TOOL, "value": "撞库工具", "context": "批量检测账号密码的工具", "confidence": 0.88},
        {"type": EntityType.ACCOUNT, "value": "@paofen888", "context": "跑分平台Telegram联系方式", "confidence": 0.95},
        {"type": EntityType.ACCOUNT, "value": "@sijiantao_shop", "context": "四件套贩卖Telegram联系方式", "confidence": 0.92},
        {"type": EntityType.PAYMENT_METHOD, "value": "BTC支付", "context": "暗网交易常用支付方式", "confidence": 0.8},
        {"type": EntityType.MALWARE, "value": "RAT远控木马", "context": "远程控制恶意软件", "confidence": 0.87},
        {"type": EntityType.SERVICE, "value": "接码平台", "context": "提供手机验证码代收服务", "confidence": 0.85},
        {"type": EntityType.SERVICE, "value": "DDoS攻击服务", "context": "按小时收费的DDoS攻击服务", "confidence": 0.82},
        {"type": EntityType.PERSON, "value": "盘总", "context": "杀猪盘项目组织者", "confidence": 0.75},
        {"type": EntityType.PERSON, "value": "水房老板", "context": "洗钱通道运营者", "confidence": 0.78},
        {"type": EntityType.TOOL, "value": "钓鱼工具包", "context": "针对中国银行的钓鱼网站套件", "confidence": 0.9},
        {"type": EntityType.CRYPTO_WALLET, "value": "bc1q...暗网收款地址", "context": "暗网市场常用BTC收款地址", "confidence": 0.7},
        {"type": EntityType.ORGANIZATION, "value": "XX菠菜平台", "context": "网络赌博平台", "confidence": 0.83},
        {"type": EntityType.TOOL, "value": "蜘蛛池", "context": "SEO黑帽技术中的链接农场工具", "confidence": 0.8},
        {"type": EntityType.IP, "value": "185.220.101.xxx", "context": "暗网市场服务器IP", "confidence": 0.65},
        {"type": EntityType.DOMAIN, "value": "darkmarketx.onion", "context": "暗网市场域名", "confidence": 0.88},
        {"type": EntityType.SERVICE, "value": "养号服务", "context": "批量培育社交媒体账号", "confidence": 0.82},
        {"type": EntityType.TOOL, "value": "AI换脸工具", "context": "用于绕过活体检测的深度伪造工具", "confidence": 0.85},
        {"type": EntityType.ORGANIZATION, "value": "XX资金盘", "context": "疑似庞氏骗局平台", "confidence": 0.8},
    ]

    entity_ids = []
    for ent_data in entities_data:
        entity = Entity(**ent_data)
        await kg.add_entity(entity)
        entity_ids.append(entity.id)

    relations_data = [
        (0, 1, RelationType.USES, "跑分平台使用猫池设备接收验证码"),
        (0, 3, RelationType.CONTROLS, "跑分平台通过此Telegram账号联系"),
        (1, 7, RelationType.USES, "猫池设备对接接码平台"),
        (4, 5, RelationType.USES, "四件套贩卖使用BTC收款"),
        (9, 0, RelationType.OPERATES, "盘总运营跑分平台"),
        (10, 0, RelationType.ASSOCIATED_WITH, "水房老板与跑分平台合作洗钱"),
        (6, 16, RelationType.LOCATED_IN, "RAT远控木马部署在暗网服务器"),
        (11, 16, RelationType.ASSOCIATED_WITH, "钓鱼工具包在暗网市场出售"),
        (13, 14, RelationType.USES, "菠菜平台使用蜘蛛池做SEO"),
        (2, 17, RelationType.USES, "撞库工具需要养号服务提供账号"),
        (18, 7, RelationType.USES, "AI换脸工具配合接码平台绕过认证"),
        (19, 10, RelationType.ASSOCIATED_WITH, "资金盘与洗钱通道关联"),
        (8, 15, RelationType.LOCATED_IN, "DDoS服务使用暗网服务器"),
        (0, 10, RelationType.USES, "跑分平台使用水房通道洗钱"),
        (3, 4, RelationType.COMMUNICATES_WITH, "两个Telegram账号在群组中互动"),
    ]

    for src_idx, tgt_idx, rel_type, evidence in relations_data:
        relation = Relation(
            source_entity_id=entity_ids[src_idx],
            target_entity_id=entity_ids[tgt_idx],
            type=rel_type,
            confidence=round(random.uniform(0.7, 0.95), 2),
            evidence=evidence,
        )
        await kg.add_relation(relation)

    await kg.save()

    logger.info(f"Database seeded: {len(RAW_INTELLIGENCE_DATA)} intelligence items, "
                f"{len(entities_data)} entities, {len(relations_data)} relations, "
                f"{len(pirs_data)} PIRs")


if __name__ == "__main__":
    asyncio.run(seed_database())
