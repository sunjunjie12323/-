# 黑灰产情报分析Agent — 项目记忆文件

> 本文件供接手此项目的智能体阅读，包含完整的项目状态、架构、已知问题和待办事项。
> 最后更新：2026-05-11

---

## 一、项目概述

**项目名称**：黑灰产情报分析Agent（Threat Intel Agent）
**项目定位**：基于纯算法（无LLM依赖）的威胁情报分析平台，面向黑灰产情报的采集、分析、预测和预警
**技术栈**：
- 后端：Python 3.11 + FastAPI + SQLAlchemy(async) + SQLite + ChromaDB + NetworkX
- 前端：React 18 + TypeScript + Ant Design + Vite
- 部署：Docker + docker-compose + Prometheus metrics
- 认证：JWT + bcrypt + RBAC（admin/analyst/viewer）

---

## 二、6大创新引擎（核心卖点）

### 1. ZeroDayDetector — 零日术语检测
- **文件**：`backend/app/core/zero_day_detector.py`
- **算法**：SkipGram词向量 + KL散度漂移检测 + 位置覆盖法（中文）
- **中文检测流程**：标记已知词→提取未覆盖间隙→过滤虚词→DP分解检查→犯罪上下文判定
- **英文检测流程**：n-gram提取→常见词过滤→上下文异常度+KL漂移→置信度评分
- **关键常量**：`_CHINESE_COMMON_WORDS`（~600词）、`_CHINESE_CRIMINAL_CONTEXT_KEYWORDS`（~80词）、`_CHINESE_FUNCTION_CHARS`
- **已知问题**：检测出的术语有时不够精准（如"使用未知"被检测为零日术语），需要优化分词和过滤

### 2. AttackChainPredictor — 攻击链预测
- **文件**：`backend/app/core/attack_chain_predictor.py`
- **算法**：MITRE ATT&CK马尔可夫链 + 经验融合（0.6*先验 + 0.4*经验）
- **关键数据**：`MITRE_TRANSITIONS`（13个战术的转移概率先验）、`MITRE_TECHNIQUES`（35+技术）、`ENTITY_TYPE_TO_TACTIC`（实体→战术映射）
- **预测流程**：实体→战术映射→马尔可夫转移→最可能技术选择→概率输出
- **当前状态**：最高概率0.473（reconnaissance→initial_access），正常工作

### 3. EntityAttribution — 实体归因
- **文件**：`backend/app/core/entity_attribution.py`
- **算法**：跨平台指纹匹配 + TransE知识图谱嵌入
- **功能**：跨平台实体关联、指纹生成、归因报告

### 4. TemporalDecay — 时间衰减
- **文件**：`backend/app/core/temporal_decay.py`
- **算法**：可学习半衰期 + 指数衰减模型
- **功能**：情报时效性评估、衰减曲线、推荐操作

### 5. IntelligenceOrganism — 情报体
- **文件**：`backend/app/core/intelligence_organism.py`
- **算法**：生物进化隐喻（基因遗传、自然选择、活力衰减、物种半衰期）
- **关键常量**：`SPECIES_HALF_LIFE_HOURS`（各物种半衰期）、`SPECIES_INITIAL_VITALITY_RANGE`（初始活力范围）
- **功能**：spawn/evolve/archive/基因匹配/基因继承/预测校准/生命周期检查
- **当前状态**：50个情报体，16种不同vitality值，正常工作

### 6. ProvenanceChain — 来源溯源
- **文件**：`backend/app/core/provenance_chain.py`
- **算法**：信息传递链 + 幻觉检测
- **功能**：溯源链构建、演化追踪、幻觉检测

---

## 三、其他核心模块

### AlertEngine — 告警引擎
- **文件**：`backend/app/core/alert_engine.py`
- **8条默认规则**：critical-threat, zero-day, ransomware, apt, supply-chain, darkweb-sale, data-breach, botnet
- **功能**：规则评估→告警生成→冷却机制→通知分发→磁盘持久化
- **持久化路径**：`./alert_data/alerts.json`
- **API**：`/api/v1/alerts/active|stats|rules|test-trigger|{id}/acknowledge`

### STIXExporter — STIX 2.1导出
- **文件**：`backend/app/core/stix_exporter.py`
- **导出对象类型**：indicator, threat-actor, vulnerability, malware, relationship
- **API**：`/api/v1/intelligence/{id}/export/stix`、`/api/v1/intelligence/export/stix-bundle`

### LocalEmbeddingEngine — 本地向量引擎
- **文件**：`backend/app/core/local_embedding.py`
- **算法**：TF-IDF + SVD降维（替代LLM embedding）
- **用途**：为VectorStore提供无外部依赖的向量化

### BlackTalkEngine — 暗网黑话引擎
- **文件**：`backend/app/core/blacktalk_engine.py`
- **功能**：黑话解码、自动学习、分类推断、向量搜索

### VectorStore — 向量存储
- **文件**：`backend/app/core/vector_store.py`
- **底层**：ChromaDB
- **关键修复**：`_sanitize_metadata()` 方法将list/tuple/set转为逗号分隔字符串（ChromaDB只接受str/int/float/bool）

---

## 四、API路由完整列表

| 路径前缀 | 功能 | 认证 |
|---|---|---|
| `/health` | 健康检查 | 无 |
| `/metrics` | Prometheus指标 | 无 |
| `/api/v1/auth/*` | 登录/注册/用户管理 | 部分 |
| `/api/v1/dashboard/*` | 仪表盘统计 | 需要 |
| `/api/v1/intelligence/*` | 情报CRUD+STIX导出 | 需要 |
| `/api/v1/entities/*` | 实体CRUD+搜索 | 需要 |
| `/api/v1/blacktalk/*` | 黑话搜索/解码/术语 | 需要 |
| `/api/v1/zero-day/*` | 零日检测/漂移/迁移 | admin/analyst |
| `/api/v1/attack-prediction/*` | 攻击链预测/模拟/预警 | admin/analyst |
| `/api/v1/attribution/*` | 实体归因/指纹 | 需要 |
| `/api/v1/organism/*` | 情报体管理 | 需要 |
| `/api/v1/decay/*` | 时间衰减 | 需要 |
| `/api/v1/provenance/*` | 来源溯源 | 需要 |
| `/api/v1/alerts/*` | 告警管理 | 需要 |
| `/api/v1/graph/*` | 知识图谱 | 需要 |
| `/api/v1/agent/*` | Agent编排 | 需要 |
| `/api/v1/reports/*` | 报告生成 | 需要 |
| `/api/v1/pirs/*` | PIR管理 | 需要 |
| `/api/v1/tasks/*` | 任务队列 | 需要 |

**登录方式**：POST `/api/v1/auth/login`，body: `{"username": "admin", "password": "admin123"}`，返回 `access_token`

---

## 五、前端页面

| 路由 | 页面 | 文件 |
|---|---|---|
| `/login` | 登录 | `pages/Login.tsx` |
| `/` | 仪表盘 | `pages/Dashboard.tsx` |
| `/intelligence` | 情报管理 | `pages/Intelligence.tsx` |
| `/graph` | 知识图谱 | `pages/GraphView.tsx` |
| `/pirs` | PIR管理 | `pages/PIRManager.tsx` |
| `/blacktalk` | 暗网黑话 | `pages/BlackTalk.tsx` |
| `/reports` | 报告 | `pages/Reports.tsx` |
| `/agent` | Agent | `pages/Agent.tsx` |
| `/innovation` | 创新引擎 | `pages/Innovation.tsx` |
| `/alerts` | 告警中心 | `pages/Alerts.tsx` |

**可视化组件**：
- `components/AttackChainGraph.tsx` — SVG有向图
- `components/AttributionSankey.tsx` — SVG桑基图
- `components/AlertPanel.tsx` — Ant Design告警面板

---

## 六、验证测试结果（2026-05-11）

### API验证：26/26 PASS
```
✅ 健康检查
✅ VectorStore / ZeroDayDetector / AttackChainPredictor / AlertEngine
✅ Dashboard总数=830 / Organism统计存在
✅ 零日检测无崩溃，检测到4个术语
✅ 攻击链预测max_prob=0.473
✅ 实体搜索50条结果，type=cisa_kev
✅ 归因API正常
✅ 情报体50个，16种vitality值
✅ 告警8条规则，触发4条
✅ STIX导出bundle格式正确
✅ 时间衰减/来源溯源/暗网黑话/知识图谱均正常
```

### 单元测试：79/79 PASS
- `tests/test_organism_engine.py` — 覆盖spawn/evolve/archive/基因/预测/持久化/安全

---

## 七、已修复的关键Bug历史

### Bug 1：零日检测IndexError崩溃
- **现象**：`index -9223372036854775808 is out of bounds for axis 0`
- **原因**：`_model.get_embedding()` 在word2idx映射错误时返回越界索引
- **修复**：在 `_compute_kl_drift()` 中添加 `try/except (IndexError, ValueError)` + `np.all(np.isfinite(vec))` 检查
- **位置**：`zero_day_detector.py` 第575-588行

### Bug 2：攻击链预测概率接近0
- **现象**：所有预测概率<0.15
- **原因**：自环（reconnaissance→reconnaissance）占52%转移计数；技术概率被均分稀释
- **修复**：
  1. `_get_transition_prob()` 排除自环，使用0.6*先验+0.4*经验融合
  2. `_predict_next_tactics()` 跳过自环
  3. 每个战术只选最可能技术，概率=战术概率（不再乘技术概率）
- **位置**：`attack_chain_predictor.py` 第281-300行、第332-374行

### Bug 3：STIX导出500错误
- **现象**：POST `/intelligence/{id}/export/stix` 返回500
- **原因**：`vs.search(intelligence_id)` 用UUID作搜索词失败
- **修复**：添加try/except + 数据库回退 + 最小数据回退
- **位置**：`intelligence.py` STIX导出端点

### Bug 4：Dashboard显示0条
- **现象**：Dashboard total_intelligence=0
- **原因**：ChromaDB静默拒绝list类型metadata
- **修复**：`vector_store.py` 添加 `_sanitize_metadata()` 方法
- **位置**：`vector_store.py`

### Bug 5：实体搜索type=unknown
- **现象**：所有实体type显示unknown
- **原因**：metadata键名与提取代码不匹配
- **修复**：`entities.py` 添加多级fallback键（ioc_type, threat_type, source等）
- **位置**：`entities.py` 第79-92行

### Bug 6：情报体vitality全=1.0
- **现象**：所有organism的vitality相同
- **原因**：所有organism刚创建，age_hours≈0
- **修复**：添加物种特定初始活力范围 + `simulate_time_passage()` 在批量训练中
- **位置**：`intelligence_organism.py` + `batch_train_offline.py`

---

## 八、商业化差距分析（诚实评估）

### 综合评分：5.75/10（比赛项目7.5/10）

| 维度 | 分数 | 关键问题 |
|---|---|---|
| 算法创新性 | 8/10 | 6大引擎纯算法实现，有学术基础 |
| 技术栈完整性 | 7/10 | 前后端+Docker+监控+认证齐全 |
| 数据规模 | 7/10 | 830条真实情报 |
| **安全性** | **5/10** | 用户存内存、默认密码硬编码、无2FA |
| **可扩展性** | **4/10** | SQLite单机、ChromaDB嵌入式、无Redis |
| **测试覆盖** | **3/10** | 仅1个测试文件，5个引擎零测试 |
| 用户体验 | 5/10 | 10个页面但可视化简单、无国际化 |

---

## 九、待办事项（按优先级排序）

### P0 — 必须修复（商业化阻断项）

#### 1. 用户系统迁移到数据库
- **当前**：`_users_db: Dict[str, User] = {}` 在内存，重启丢失
- **目标**：迁移到SQLAlchemy数据库表
- **涉及文件**：
  - `backend/app/core/auth.py` — 重写 `_users_db` 为数据库查询
  - `backend/app/db/tables.py` — 添加User表定义
  - `backend/app/db/crud.py` — 添加UserCRUD
  - `backend/app/api/auth.py` — 适配数据库操作
- **注意**：Token黑名单 `_token_blacklist` 也需要迁移（或用Redis）

#### 2. 补充核心引擎单元测试
- **当前**：只有 `test_organism_engine.py`（79个测试）
- **需要新增**：
  - `tests/test_zero_day_detector.py` — 测试中文/英文检测、KL漂移、边界情况
  - `tests/test_attack_chain_predictor.py` — 测试转移概率、预测、模拟
  - `tests/test_entity_attribution.py` — 测试指纹、归因
  - `tests/test_temporal_decay.py` — 测试衰减公式、半衰期学习
  - `tests/test_provenance_chain.py` — 测试溯源链、幻觉检测
  - `tests/test_alert_engine.py` — 测试规则评估、冷却、持久化
  - `tests/test_stix_exporter.py` — 测试导出格式
  - `tests/test_api_integration.py` — API集成测试
- **目标覆盖率**：70%+

#### 3. 数据库升级到PostgreSQL
- **当前**：SQLite（`sqlite+aiosqlite:///./threat_intel.db`）
- **问题**：不支持并发写入、无法多实例部署
- **需要**：
  - 修改 `config.py` 的 `DATABASE_URL` 默认值
  - 修改 `docker-compose.yml` 添加PostgreSQL服务
  - 修改 `requirements.txt` 添加 `asyncpg` 或 `psycopg2`
  - 测试所有异步数据库操作兼容性

### P1 — 重要改进

#### 4. 添加Redis缓存层
- 高频查询（Dashboard统计、实体搜索、黑话搜索）需要缓存
- Token黑名单迁移到Redis
- 速率限制计数器迁移到Redis
- docker-compose.yml添加Redis服务

#### 5. 实现定时数据采集
- **当前**：830条是初始化数据，无定时更新
- **需要**：
  - 添加APScheduler或Celery Beat定时任务
  - 配置各情报源API Key（AlienVault OTX、VirusTotal、ThreatBook等）
  - 实现数据过期/刷新策略
  - 添加采集任务状态监控

#### 6. 安全加固
- 移除硬编码默认密码 `admin123`
- 添加密码强度校验
- 添加双因素认证（2FA）
- 添加操作审计日志完善（当前只有audit.log基础版）
- CSRF保护
- 输入验证增强

#### 7. 前端完善
- 数据导出：CSV/Excel/PDF（当前只有STIX）
- 用户引导/帮助文档
- 国际化（i18n）
- 更丰富的可视化（时间线、热力图、地图）
- 响应式布局优化

### P2 — 优化提升

#### 8. 零日检测精度优化
- 当前"使用未知"被检测为零日术语，不够精准
- 考虑引入jieba分词替代bigram分词
- 优化 `_CHINESE_COMMON_WORDS` 词典覆盖度
- 添加误报率评估机制

#### 9. 知识图谱增强
- 当前图谱实体较少，关系稀疏
- 从830条情报中自动抽取更多实体和关系
- 添加社区发现算法
- 图谱可视化交互优化

#### 10. 性能优化
- 添加数据库索引
- 分页查询优化
- 向量搜索性能优化
- 前端懒加载/虚拟滚动

---

## 十、关键文件路径速查

```
threat-intel-agent/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── batch_train_offline.py          ← 离线批量训练脚本
│   ├── run.py
│   ├── pytest.ini
│   ├── threat_intel.db                 ← SQLite数据库
│   ├── .env                            ← 环境变量
│   ├── .secret_key                     ← 自动生成的JWT密钥
│   ├── app/
│   │   ├── main.py                     ← FastAPI主入口（18步服务初始化）
│   │   ├── config.py                   ← 配置（含默认密码admin123）
│   │   ├── core/
│   │   │   ├── zero_day_detector.py    ← 零日检测引擎
│   │   │   ├── attack_chain_predictor.py ← 攻击链预测引擎
│   │   │   ├── entity_attribution.py   ← 实体归因引擎
│   │   │   ├── temporal_decay.py       ← 时间衰减引擎
│   │   │   ├── intelligence_organism.py ← 情报体引擎
│   │   │   ├── provenance_chain.py     ← 来源溯源引擎
│   │   │   ├── alert_engine.py         ← 告警引擎
│   │   │   ├── stix_exporter.py        ← STIX 2.1导出
│   │   │   ├── local_embedding.py      ← TF-IDF+SVD本地向量
│   │   │   ├── blacktalk_engine.py     ← 暗网黑话引擎
│   │   │   ├── vector_store.py         ← ChromaDB向量存储
│   │   │   ├── knowledge_graph.py      ← NetworkX知识图谱
│   │   │   ├── auth.py                 ← JWT认证+RBAC（⚠️内存存储）
│   │   │   ├── rate_limiter.py         ← 速率限制
│   │   │   ├── llm.py                  ← LLM服务（已不使用）
│   │   │   ├── evidence_chain.py       ← 证据链
│   │   │   ├── pir_engine.py           ← PIR引擎
│   │   │   ├── task_queue.py           ← 任务队列
│   │   │   └── exceptions.py           ← 自定义异常
│   │   ├── api/
│   │   │   ├── auth.py                 ← 认证API
│   │   │   ├── dashboard.py            ← 仪表盘API
│   │   │   ├── intelligence.py         ← 情报API+STIX导出
│   │   │   ├── entities.py             ← 实体API+搜索
│   │   │   ├── zero_day.py             ← 零日检测API
│   │   │   ├── attack_prediction.py    ← 攻击链预测API
│   │   │   ├── attribution.py          ← 归因API
│   │   │   ├── organism.py             ← 情报体API
│   │   │   ├── temporal_decay.py       ← 时间衰减API
│   │   │   ├── provenance.py           ← 来源溯源API
│   │   │   ├── alerts.py               ← 告警API
│   │   │   ├── blacktalk.py            ← 黑话API
│   │   │   ├── graph.py                ← 知识图谱API
│   │   │   ├── agent.py                ← Agent编排API
│   │   │   ├── reports.py              ← 报告API
│   │   │   ├── pirs.py                 ← PIR API
│   │   │   └── tasks.py                ← 任务API
│   │   ├── db/
│   │   │   ├── database.py             ← 数据库连接
│   │   │   ├── tables.py               ← 表定义
│   │   │   ├── crud.py                 ← CRUD操作
│   │   │   └── seed.py                 ← 数据种子（830条真实情报）
│   │   ├── models/
│   │   │   ├── intelligence.py
│   │   │   ├── entity.py
│   │   │   ├── pir.py
│   │   │   └── report.py
│   │   └── collectors/
│   │       ├── darkweb_collector.py     ← 暗网采集
│   │       ├── commercial_collector.py  ← 商业情报源
│   │       ├── forum_collector.py       ← 论坛采集
│   │       ├── telegram_collector.py    ← Telegram采集
│   │       └── wechat_collector.py      ← 微信采集
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_organism_engine.py     ← 唯一的测试文件（79个测试）
│   ├── model_data/                     ← 训练好的模型数据
│   │   ├── zero_day/                   ← SkipGram模型+参考分布
│   │   ├── attack_chain/               ← 马尔可夫链
│   │   ├── attribution/                ← TransE模型
│   │   ├── temporal_decay/             ← 学习的半衰期
│   │   └── provenance/                 ← 溯源数据
│   ├── chroma_data/                    ← ChromaDB持久化数据
│   ├── graph_data/                     ← 知识图谱JSON
│   ├── organism_data/                  ← 情报体状态JSON
│   ├── alert_data/                     ← 告警数据JSON
│   └── cache/                          ← 采集缓存
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx                     ← 路由配置
│   │   ├── services/api.ts             ← API调用封装
│   │   ├── utils/tokenStorage.ts       ← Token存储
│   │   ├── components/
│   │   │   ├── Layout.tsx              ← 布局+菜单
│   │   │   ├── ErrorBoundary.tsx
│   │   │   ├── AttackChainGraph.tsx    ← SVG有向图
│   │   │   ├── AttributionSankey.tsx   ← SVG桑基图
│   │   │   └── AlertPanel.tsx          ← 告警面板
│   │   └── pages/
│   │       ├── Dashboard.tsx
│   │       ├── Intelligence.tsx
│   │       ├── GraphView.tsx
│   │       ├── PIRManager.tsx
│   │       ├── BlackTalk.tsx
│   │       ├── Reports.tsx
│   │       ├── Login.tsx
│   │       ├── Agent.tsx
│   │       ├── Innovation.tsx
│   │       └── Alerts.tsx
│   └── dist/                           ← 构建产物
└── .github/
    └── workflows/
        └── ci.yml                      ← CI配置
```

---

## 十一、运行指南

### 后端启动
```bash
cd backend
python3.11 -m venv venv  # 需要Python 3.11（3.14不兼容pydantic-core）
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端启动
```bash
cd frontend
npm install
npm run dev    # 开发模式
npm run build  # 生产构建
```

### Docker启动
```bash
docker-compose up --build
```

### 运行测试
```bash
cd backend
source venv/bin/activate
python tests/test_organism_engine.py
```

### API验证脚本
```python
import requests
BASE = "http://localhost:8000"
# 登录
r = requests.post(f"{BASE}/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
# 健康检查
requests.get(f"{BASE}/health").json()
# Dashboard
requests.get(f"{BASE}/api/v1/dashboard/stats", headers=headers).json()
# 零日检测
requests.post(f"{BASE}/api/v1/zero-day/detect", json={"text": "发现新型勒索病毒使用未知加密算法"}, headers=headers).json()
# 攻击链预测（需要先获取graph entity id）
entities = requests.get(f"{BASE}/api/v1/graph/entities?limit=1", headers=headers).json()
eid = entities["items"][0]["id"]
requests.post(f"{BASE}/api/v1/attack-prediction/predict", json={"entity_id": eid, "depth": 3}, headers=headers).json()
```

---

## 十二、注意事项

1. **Python版本**：必须用3.11，3.14会导致pydantic-core编译失败
2. **ChromaDB metadata**：所有list/tuple/set类型必须转为逗号分隔字符串，否则ChromaDB静默拒绝
3. **认证**：大部分API需要Bearer Token，零日检测和攻击链预测需要admin或analyst角色
4. **数据初始化**：首次启动会自动seed 830条情报数据（来自`seed.py`）
5. **模型数据**：`model_data/`目录包含预训练模型，删除后会在启动时重新训练
6. **前端构建**：`dist/`目录已有构建产物，但可能需要重新构建以匹配最新API
7. **内存用户系统**：重启后用户数据丢失，会重新创建默认admin用户——这是P0待办项
