# 谛观 GreenwashGuard — 技术设计文档

> **基于三异构大语言模型多数投票机制的A股上市公司环境披露"漂绿"风险测算系统**
>
> 参考论文：*How Environmental Courts Inhibit Corporate Greenwashing—Evidence from Heterogeneous LLM Measures*

---

## 一、项目概述

### 1.1 问题背景

"漂绿"（Greenwashing）是指企业通过空泛、修辞性的正面环境表述来营造环保形象，但缺乏实质性行动和数据支撑的行为。传统人工编码方式难以大规模、低成本地识别此类行为。

### 1.2 系统目标

构建一套**可复现、可扩展**的自动化漂绿测算系统：
- 对A股上市公司年报（MD&A章节）进行环境语句智能分类
- 采用三异构LLM集成推理降低单一模型偏差
- 计算企业层面"GW漂绿指数"并与同行业基准对比
- 通过Web界面提供交互式分析、实时进度推送和可视化展示
- 一键静默启动，无控制台窗口，自动打开浏览器

### 1.3 核心创新

| 创新点 | 技术实现 |
|--------|---------|
| 三异构模型多数投票 | DeepSeek-R1（推理增强）+ Qwen-Max（中文优化）+ GLM-4.7（通用），三模型独立判断后投票 |
| 分类-情感两阶段 | 先分类（实质性/描述性/非环保），仅对描述性句打情感分，减少噪声 |
| 行业基准动态计算 | 同行业同年份语调中位数作为基准，GW = max(0, 企业语调 - 行业中位数) |
| SSE实时进度推送 | 分析过程中通过Server-Sent Events推送进度、模型分歧、中间结果 |
| 熔断降级机制 | LLM API失败时自动熔断，可降级到Mock模式保证体验 |
| 单端口一体化部署 | 后端直接托管前端静态文件，无需额外Nginx，一个端口搞定 |
| 静默启动体验 | VBS+pythonw后台启动，无黑框，自动打开浏览器 |

---

## 二、系统架构

### 2.1 技术栈

```
┌─────────────────────────────────────────────────────────┐
│                     浏览器                                │
│              访问 http://localhost:8000                   │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / SSE（统一端口）
┌──────────────────────▼──────────────────────────────────┐
│                FastAPI 后端 (单端口 8000)                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │  /           → 前端静态文件 (Vue 3 SPA)          │   │
│  │  /assets/*   → JS/CSS/图片等静态资源             │   │
│  │  /api/*      → 后端API接口                       │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────┐  ┌───────────┐  ┌────────────┐            │
│  │ API路由层 │  │ 编排服务   │  │ LLM客户端   │            │
│  │ (REST+SSE)│→│Orchestrator│→│(限流/熔断/重试)│           │
│  └──────────┘  └─────┬─────┘  └──────┬─────┘            │
│                      │               │                   │
│  ┌──────────┐  ┌─────▼─────┐  ┌──────▼─────┐            │
│  │ Pydantic │  │ 分类/情感  │  │ 三模型融合  │            │
│  │ Schema  │  │ 服务      │  │ (投票/平均) │            │
│  └──────────┘  └───────────┘  └────────────┘            │
│                      │                                   │
│  ┌──────────┐  ┌─────▼─────┐  ┌────────────┐            │
│  │ SQLAlchemy│  │ GW计算器  │  │ 行业基准   │            │
│  │ ORM      │  │           │  │ 服务       │            │
│  └─────┬────┘  └───────────┘  └────────────┘            │
│        │                                                 │
└────────┼─────────────────────────────────────────────────┘
         │
┌────────▼────────┐  ┌─────────────┐  ┌──────────────────┐
│  SQLite/Postgres │  │ DeepSeek API│  │ 巨潮资讯爬虫     │
│   (持久化)       │  │ Qwen API    │  │ CNInfo Crawler  │
│                  │  │ GLM API     │  │ PDF Parser       │
└─────────────────┘  └─────────────┘  └──────────────────┘
```

### 2.2 模块划分

| 模块 | 路径 | 职责 |
|------|------|------|
| 静态文件托管 | `app/main.py` | 托管Vue前端dist产物，SPA fallback路由 |
| API路由 | `app/api/` | HTTP接口、SSE流式推送、参数校验 |
| 编排服务 | `app/services/analysis_orchestrator.py` | 核心流程编排、进度回调 |
| LLM客户端 | `app/services/llm_client.py` | 统一API调用、令牌桶限流、熔断器、指数退避重试 |
| 分类器 | `app/services/classifier.py` | 调用LLM完成三分类（substantive/descriptive/non_env） |
| 情感分析 | `app/services/sentiment.py` | 对描述性语句做[-1,1]情感打分 |
| 模型融合 | `app/services/fusion.py` | 多数投票（分类）+ 集成平均（情感）、Fleiss' Kappa |
| GW计算器 | `app/services/calculator.py` | 语调聚合、Winsorize缩尾、GW指数计算 |
| 行业基准 | `app/services/industry_service.py` | 动态行业中位数、预警阈值（80分位）、风险等级标记 |
| Mock服务 | `app/services/mock_service.py` | 离线演示模式，关键词规则模拟LLM行为 |
| PDF解析 | `app/services/pdf_parser.py` | 表格转文本、ESG指标提取、页码定位 |
| 数据模型 | `app/models/` | SQLAlchemy ORM：Company/AnalysisRecord/Sentence/IndustryBenchmark |
| 数据校验 | `app/schemas/` | Pydantic v2响应模型 |
| 启动管理器 | `launcher.py` | 自动检查依赖、初始化数据库、后台启动服务、打开浏览器 |
| 工具脚本 | `scripts/` | 初始化数据库、种子数据、批量流水线、爬虫 |

---

## 三、核心算法流程

### 3.1 完整分析管线

```
输入: stock_code / PDF文件 / 文本
  ↓
① 缓存检查 → 数据库已有最新结果则直接返回
  ↓
② 文本获取
   ├─ 股票代码: 从本地MD&A目录读取 / 巨潮资讯爬虫抓取年报
   └─ PDF上传: pdfplumber解析 → 表格转文本 → 章节定位
  ↓
③ 文本预处理
   ├─ 正则分句（按。！；？等）
   ├─ 去除表格数据、页眉页脚、短句子
   └─ 环境关键词过滤（强/弱关键词两级）
         ├─ 包含强关键词 → 直接入选
         ├─ 含弱关键词但含排除词 → 排除
         └─ 其他 → 判定为non_env
  ↓
④ 三模型并行分类 (SSE推送: 分类进度)
   ├─ DeepSeek-R1  → {substantive/descriptive/non_env}
   ├─ Qwen-Max     → {substantive/descriptive/non_env}
   ├─ GLM-4.7      → {substantive/descriptive/non_env}
   └─ 限流保护: 令牌桶 20 req/min，失败指数退避重试3次
  ↓
⑤ 多数投票融合
   ├─ 三模型一致 → unanimous, confidence=1.0
   ├─ 两模型一致 → majority, confidence=0.67
   └─ 全分歧    → full_divergence, 标记needs_review
   ├─ Fleiss' Kappa 计算模型一致性
   └─ 分歧计数 divergence_count
  ↓
⑥ 情感分析 (仅描述性语句)
   ├─ 三模型分别对描述性句打[-1,1]情感分
   └─ 集成平均: (ds+qw+glm)/3，计算std衡量分歧
  ↓
⑦ Winsorize缩尾 (1%/99%分位) → 抑制极端值
  ↓
⑧ 计算企业语调 tone_score = 描述性语句情感均值
  ↓
⑨ 行业基准: 取同行业同年份tone_score中位数
  ↓
⑩ GW指数 = max(0, tone_score - industry_median)
  ↓
⑪ 风险等级: GW ≥ 行业80分位 → "预警"，否则"正常"
  ↓
⑫ 持久化到数据库 → SSE推送最终结果
```

### 3.2 分类体系

| 标签 | 含义 | 是否参与GW计算 |
|------|------|--------------|
| `substantive`（实质性陈述） | 包含具体数据、量化目标、可验证行动（如"环保投入5000万元，COD排放下降15%"） | 否 |
| `descriptive`（描述性陈述） | 空泛口号、修辞性表述，无具体数据支撑（如"高度重视绿色发展，积极践行双碳战略"） | **是**（漂绿主要来源） |
| `non_env`（非环保语句） | 虽含环保关键词但实际讨论其他内容 | 否 |

### 3.3 GW漂绿指数

$$GW_i = \max(0,\; Tone_i - Median\{Tone_j \mid j \in Industry_i, Year_j = Year_i\})$$

- **Tone_i**：企业描述性语句情感均值，[-1,1]区间，越正表示修辞越正面
- **行业中位数**：同年同行业所有企业Tone的中位数（剔除金融类、ST类）
- **max(0, ...)**：语调低于行业基准的企业不视为漂绿（GW=0）
- **预警阈值**：全市场GW的80%分位数，超过则标记为"预警"

---

## 四、LLM客户端设计

### 4.1 容错机制

| 机制 | 实现 |
|------|------|
| 令牌桶限流 | 每模型 20 req/min，防止触发API频率限制 |
| 熔断器（Circuit Breaker） | 连续5次失败后打开熔断，30秒后半开试探，恢复后闭合 |
| 指数退避重试 | 失败后等待 2s/4s/8s 重试3次 |
| 超时控制 | 单次请求60秒超时 |
| Mock降级 | 三模型全部不可用时自动切换到Mock模式（关键词规则） |

### 4.2 Prompt设计

分类Prompt采用角色定义 + 标签说明 + 正反例 + 思维链格式：

```
你是一位专业的ESG分析师，判断企业年报中的环境相关语句属于以下哪一类：
A. 实质性陈述 - 包含具体数据、可验证行动、定量目标
B. 描述性陈述 - 空泛口号、修辞性表述、无数据支撑
C. 非环保语句 - 与环境无关
请按 <think>分析</think><result>A/B/C</result> 格式输出。
```

### 4.3 模型分工

| 模型 | 优势 | 角色 |
|------|------|------|
| DeepSeek-R1 | 推理能力强，思维链深度分析 | 主推理模型 |
| Qwen-Max | 中文语料丰富，金融领域理解好 | 中文语义校准 |
| GLM-4.7 | 响应速度快，通用性好 | 快速验证模型 |

---

## 五、数据模型

### 5.1 ER关系

```
Company (企业)
  ├──< AnalysisRecord (分析记录，一年一条)
  │      └──< Sentence (语句级结果，最新年有)
  └──< IndustryBenchmark (行业基准，一年一行业一条)
```

### 5.2 核心表结构

**Company（企业表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| stock_code | String(10) | 股票代码（唯一） |
| company_name | String(100) | 公司全称 |
| short_name | String(50) | 简称 |
| industry | String(20) | 申万一级行业 |
| is_a_share | Boolean | 是否A股 |
| is_seed | Boolean | 是否种子演示数据 |
| is_st | Boolean | 是否ST/*ST/PT |
| is_active | Boolean | 是否活跃 |

**AnalysisRecord（分析记录表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| company_id | FK → Company | |
| year | Integer | 年度 |
| total_sentences / env_sentences | Integer | 总句数/环境句数 |
| substantive_count / descriptive_count / non_env_count | Integer | 三类语句数 |
| tone_score | Float | 描述性语句情感均值[-1,1] |
| industry_median_tone | Float | 行业语调中位数 |
| gw_index | Float [0,2] | GW漂绿指数 |
| risk_level | String | "正常"/"预警" |
| fleiss_kappa | Float | 三模型一致性Kappa |
| divergence_count | Integer | 全分歧语句数 |
| data_source_type | String | MD&A/PDF/Mock |
| is_latest | Boolean | 是否最新年度 |

**Sentence（语句级结果表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| analysis_record_id | FK → AnalysisRecord | |
| sentence_text | Text | 原文 |
| deepseek_result / qwen_result / glm_result | String | 三模型原始分类 |
| final_category | String | 投票后最终分类 |
| vote_type | String | unanimous/majority/full_divergence |
| confidence | Float | 置信度 |
| sentiment_score | Float [-1,1] | 情感分数（仅描述性） |
| sentiment_std | Float | 三模型情感标准差 |
| needs_review | Boolean | 是否需人工复核 |

---

## 六、API接口

所有接口前缀 `/api`，统一JSON响应格式。前端静态文件托管在 `/` 和 `/assets/`。

### 6.1 核心接口

| 方法 | 路径 | 功能 | SSE |
|------|------|------|-----|
| POST | `/api/analysis/stream/{stock_code}` | 流式分析企业（股票代码） | ✅ |
| POST | `/api/pdf/analyze` | PDF上传分析 | ✅ |
| GET | `/api/analysis/result/{stock_code}` | 获取分析结果 | |
| GET | `/api/dashboard` | 仪表盘汇总数据 | |
| GET | `/api/dashboard/top10` | Top10高风险企业 | |
| GET | `/api/dashboard/distribution` | GW指数分布 | |
| GET | `/api/dashboard/china_map` | 地图数据（按省） | |
| GET | `/api/companies/` | 企业列表（搜索/分页） | |
| GET | `/api/companies/{code}/trend` | 企业历史趋势 | |
| GET | `/api/companies/{code}/sentences` | 语句级分类结果 | |
| GET | `/api/watchlist/` | 关注列表 | |
| POST | `/api/watchlist/{code}` | 添加关注 | |
| DELETE | `/api/watchlist/{code}` | 取消关注 | |
| GET | `/api/industries` | 行业列表 | |
| GET | `/health` | 健康检查 | |
| GET | `/` | 前端首页 | |

### 6.2 SSE事件类型

| 事件 | 触发时机 | 数据字段 |
|------|---------|---------|
| `connected` | 连接建立 | |
| `progress` | 每个阶段更新 | percent, stage, message |
| `model_classified` | 单句分类完成 | idx, total, category |
| `phase` | 大阶段切换 | phase, description |
| `complete` | 分析完成 | 完整result对象 |
| `error` | 出错 | message |

### 6.3 响应示例

```json
{
  "code": 200,
  "data": {
    "company": {"code": "002594", "name": "比亚迪", "industry": "汽车"},
    "gw_index": 0.087,
    "risk_level": "正常",
    "tone_score": 0.338,
    "industry_median_tone": 0.251,
    "fleiss_kappa": 0.84,
    "counts": {"substantive": 18, "descriptive": 10, "non_env": 62}
  }
}
```

---

## 七、前端架构

### 7.1 组件结构

```
App.vue
├── HeroBanner.vue        # 首屏搜索框 + 结果展示（合并）
├── PdfUpload.vue         # PDF拖拽上传
├── ResultCard.vue        # 企业结果卡片（GW指数环形图）
├── SentenceList.vue      # 语句分类列表（三类Tab切换）
├── ChinaMap.vue          # 中国省份风险地图（ECharts）
├── Top10Grid.vue         # Top10高风险企业
├── MethodSteps.vue       # 方法学说明 + 合作伙伴Logo
└── NavBar.vue            # 顶部导航
```

### 7.2 状态管理（Pinia）

- `analysis`：当前分析状态、进度、结果数据
- `watchlist`：关注列表（localStorage持久化）
- `dashboard`：仪表盘汇总数据

### 7.3 构建产物

前端通过 `npm run build` 打包到 `frontend/dist/` 目录，后端启动时自动检测并托管该目录：
- `/` → 返回 `index.html`
- `/assets/*` → 返回JS/CSS/图片等静态资源
- 其他前端路由 → SPA fallback 到 `index.html`
- `/api/*` → 后端API接口

---

## 八、配置与部署

### 8.1 环境要求

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10+ | 后端运行环境 |
| pip | 最新版 | Python包管理器 |
| 浏览器 | Chrome/Edge/Firefox | 访问系统 |

> 注意：Node.js 仅在**重新开发构建前端**时需要，普通使用已包含预构建的dist目录，无需安装Node.js！

### 8.2 一键启动（推荐，Windows）

**双击 `启动系统.vbs`** 即可：
1. 自动检查Python环境
2. 自动检查并安装Python依赖（首次运行）
3. 自动创建.env配置文件（首次运行）
4. 自动初始化数据库（首次运行）
5. 后台静默启动服务（无黑框/无控制台窗口）
6. 等待服务就绪后自动打开浏览器

停止服务：**双击 `停止系统.vbs`**

### 8.3 环境变量（backend/.env）

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `APP_MODE` | 否 | `mock` | `mock`(离线演示，无需API Key) / `real`(调用真实LLM) |
| `DATABASE_URL` | 否 | sqlite:///./data/db/greenwash_guard.db | SQLite或PostgreSQL连接串 |
| `DEEPSEEK_API_KEY` | real模式 | - | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | 否 | https://api.deepseek.com/v1 | |
| `DEEPSEEK_MODEL` | 否 | deepseek-reasoner | |
| `QWEN_API_KEY` | real模式 | - | 通义千问API Key |
| `QWEN_MODEL` | 否 | qwen-max | |
| `GLM_API_KEY` | real模式 | - | 智谱GLM API Key |
| `GLM_MODEL` | 否 | glm-4.7 | |
| `MDA_ROOT` | 否 | data/mda | 本地MD&A文本目录路径 |
| `LOG_LEVEL` | 否 | INFO | 日志级别 |

> 默认使用Mock模式，无需配置任何API Key即可体验完整功能。

### 8.4 开发模式（开发者）

```bash
# 后端开发（需要Python 3.10+）
cd backend
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000

# 前端开发（需要Node.js 18+）
cd frontend
npm install
npm run dev   # 访问 http://localhost:5173，API代理到8000
```

### 8.5 手动启动（无VBS情况）

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 然后浏览器访问 http://localhost:8000
```

---

## 九、测试

```bash
cd backend
python -m pytest tests/ -v
```

测试覆盖：
- 多数投票/集成平均算法
- 令牌桶限流/熔断器
- LLM响应解析（分类/情感）
- GW指数计算边界情况
- 文本工具（分句、关键词、缩尾）
- Mock分类/情感确定性
- 日志/请求ID

---

## 十、与论文方法论的对应

| 论文章节 | 系统实现 |
|---------|---------|
| 三异构模型独立判别 | `llm_client.py` 三个独立API调用 |
| 多数投票确权 | `fusion.py: majority_vote()` |
| Fleiss' Kappa一致性 | `fusion.py: fleiss_kappa()` |
| 描述性语句情感均值 | `calculator.py: compute_company_tone()` |
| Winsorize 1%/99%缩尾 | `text_utils.py: winsorize()` |
| 行业-年度中位数基准 | `industry_service.py: compute_industry_benchmarks()` |
| GW = max(0, Tone - Median) | `calculator.py: compute_gw_index()` |
| 剔除金融类、ST类 | `company.py: FINANCIAL_INDUSTRIES` |
| MD&A文本提取 | `cninfo_crawler.py` + 本地MD&A目录 |

---

## 十一、文件结构（完整）

```
greenwashguard/
│
├── 启动系统.vbs                     # ✅ 一键静默启动（推荐）
├── 停止系统.vbs                     # 停止后台服务
├── launcher.py                      # 启动管理器（VBS调用此文件）
├── launcher.log                     # 启动日志（排查问题用）
│
├── README.md                        # 项目说明文档
├── technical_design.md              # 本文档（技术设计）
├── .gitignore                       # Git忽略规则
├── .gitattributes                   # Git属性配置
│
├── backend/                         # FastAPI 后端
│   ├── app/
│   │   ├── main.py                  # FastAPI入口（含静态文件托管）
│   │   ├── api/                     # API路由
│   │   │   ├── stream_analysis.py   # SSE流式分析（核心）
│   │   │   ├── pdf_analysis.py      # PDF上传分析
│   │   │   ├── dashboard.py         # 仪表盘接口
│   │   │   ├── companies.py         # 企业查询
│   │   │   ├── analysis.py          # 分析结果查询
│   │   │   └── watchlist.py         # 关注列表
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings 环境变量
│   │   │   ├── database.py          # SQLAlchemy引擎+Session
│   │   │   ├── utils.py             # SSE格式化等公共函数
│   │   │   └── logging_setup.py     # 日志系统
│   │   ├── models/                  # SQLAlchemy ORM模型
│   │   ├── schemas/                 # Pydantic数据校验
│   │   └── services/                # 业务逻辑层
│   │       ├── analysis_orchestrator.py  # 分析编排+进度推送
│   │       ├── llm_client.py             # LLM客户端(限流/熔断/重试)
│   │       ├── classifier.py             # 语句分类器
│   │       ├── sentiment.py              # 情感分析器
│   │       ├── fusion.py                 # 多数投票+集成平均
│   │       ├── calculator.py             # GW指数计算
│   │       ├── industry_service.py       # 行业基准+风险等级
│   │       ├── mock_service.py           # Mock模式(规则模拟)
│   │       ├── text_utils.py             # 分句/关键词/缩尾
│   │       ├── pdf_parser.py             # PDF解析+表格处理
│   │       └── cninfo_crawler.py         # 巨潮年报爬虫
│   ├── scripts/                     # 工具脚本
│   │   ├── init_db.py               # 初始化数据库
│   │   ├── seed_data.py             # 种子演示数据
│   │   └── ...
│   ├── tests/                       # 单元测试
│   ├── data/                        # 数据文件（行业映射等）
│   ├── requirements.txt             # Python依赖
│   ├── .env.example                 # 环境变量模板
│   └── .env                         # 本地配置(不提交Git)
│
├── frontend/                        # Vue 3 前端
│   ├── dist/                        # ✅ 预构建产物（直接使用，无需Node.js）
│   │   ├── index.html
│   │   ├── assets/                  # JS/CSS/图片
│   │   └── favicon.svg
│   ├── src/                         # 源代码（开发者用）
│   │   ├── api/                     # Axios封装
│   │   ├── components/              # Vue组件
│   │   ├── stores/                  # Pinia状态
│   │   ├── App.vue
│   │   └── main.js
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
└── data/                            # （可选）本地MD&A文本数据
    └── CMDA_管理层讨论与分析_ALL/
```

### 隐藏文件/文件夹说明

| 名称 | 说明 | 是否需要提交Git | 压缩包是否包含 |
|------|------|----------------|---------------|
| `.git/` | Git版本控制目录 | ✅ 自动生成 | ❌ 不要手动压缩（否则会很大） |
| `.gitignore` | Git忽略规则 | ✅ 需要 | ✅ 需要 |
| `.gitattributes` | Git属性配置 | ✅ 需要 | ✅ 需要 |
| `.env` | 本地环境变量（含密钥） | ❌ 已忽略 | ❌ 不要包含 |
| `.env.example` | 环境变量模板 | ✅ 需要 | ✅ 需要 |
| `.server.pid` | 运行时PID文件 | ❌ 自动生成 | ❌ 不要包含 |
| `__pycache__/` | Python字节码缓存 | ❌ 已忽略 | ❌ 不要包含 |
| `node_modules/` | 前端依赖包 | ❌ 已忽略 | ❌ 不要包含（dist已编译好） |
| `*.db / *.sqlite` | SQLite数据库文件 | ❌ 已忽略 | ❌ 不要包含（启动时自动创建） |
| `*.pyc` | Python编译文件 | ❌ 已忽略 | ❌ 不要包含 |
| `.vscode/` `.idea/` | IDE配置 | ❌ 已忽略 | ❌ 不要包含 |
| `launcher.log` | 启动日志 | ❌ 运行时生成 | ❌ 不要包含 |
| `.npmrc` | npm配置 | 可选 | 可选 |
| `*.txt`（readme_*.txt） | 子目录说明文件 | 可选 | 可选 |

> **压缩包建议**：只保留必要的代码和配置文件，排除 `node_modules/`、`data/` 下的大量txt文件（如需演示数据可保留少量样本）、`__pycache__/`、`*.db`、`.env`、`.git/`、`launcher.log` 等。使用Git归档或 `git archive` 命令可以自动排除这些文件。
