# 🌿 谛观 GreenwashGuard

> **基于异构大语言模型集成推理的企业漂绿风险监测系统**
>
> GreenwashGuard — Heterogeneous LLM Ensemble Inference for Corporate Greenwashing Detection

---

## 📋 项目简介

"谛观 GreenwashGuard" 是一个面向**银行绿色信贷贷后管理**、**绿色债券存续期管理**等机构的企业漂绿风险监测工具。系统通过三个异构大语言模型（DeepSeek-R1-32B、Qwen-3-32B、GLM-4.7）对企业年报 MD&A 章节做**逐句分类**（实质性陈述 / 描述性陈述 / 非环保语句），多数投票确权，结合**语境情感打分**与**行业基准修正**，合成 **"GW 指数"** 衡量漂绿风险。

### ✨ 核心功能

| 功能                      | 说明                                                                                                                 |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| 📊**仪表盘**              | Top10 风险企业卡片、关注列表、风险分级规则、方法说明                                                                 |
| 🔍**单企业查询**          | 搜索企业，展示 GW 指数、风险等级、语句分类详情、历史趋势                                                             |
| 📄**PDF上传分析**         | 切换到"PDF上传"模式，上传年报/ESG报告PDF文件，系统解析文本并执行完整的三模型分析流程，作为搜索查询之外的补充输入方式 |
| 🤖**三模型集成推理**      | DeepSeek-R1 + Qwen-3 + GLM-4.7 独立推理 + 多数投票融合 + 语境情感打分                                                |
| ⚡**SSE流式推送**          | 实时 Server-Sent Events 推送分析进度（语句分类进度、情感打分进度、结果汇总），全异步架构                              |
| 🛡️**LLM调用保护**         | 令牌桶限流（QPS控制）、熔断器（连续失败自动降级）、指数退避重试（智能错误类型判断）                                  |
| 📋**结构化日志**           | 请求ID追踪（X-Request-ID）、请求耗时/状态码记录、LLM调用指标统计（成功率/延迟/Token/模型分布）                       |
| 🎭**Mock 模式**            | 无需 API Key 即可演示完整功能，使用确定性种子生成可复现的模拟数据                                                     |
| 🧪**单元测试**             | 81 个测试用例覆盖分类、情感、融合、计算、LLM客户端、限流熔断、日志系统等核心模块                                     |
| 🌱**绿色主题**             | 森林绿配色方案，符合 WCAG AA 级无障碍标准，响应式设计                                                                |

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────┐
│                    前端 (Vue 3)                   │
│  Vite + Pinia + ECharts + Vue Router             │
│  http://localhost:5173                           │
└──────────────────┬──────────────────────────────┘
                   │ REST API (JSON)
┌──────────────────▼──────────────────────────────┐
│                  后端 (FastAPI)                   │
│  Python 3.10+ + SQLAlchemy 2.0 + Pydantic        │
│  http://localhost:8000  |  /docs (Swagger)       │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              数据库 (SQLite → PostgreSQL)         │
│  企业信息 | 分析记录 | 语句分类 | 行业基准 | 关注列表  │
└─────────────────────────────────────────────────┘
```

### 核心算法流程

```
企业年报MD&A章节
    ↓
语句切分与环保相关性过滤
    ↓
三大异构 LLM 独立推理
├─ DeepSeek-R1-32B（推理专家）
├─ Qwen-3-32B（中文专家）
└─ GLM-4.7（通用对话模型）
    ↓
多数投票确权（Fleiss' Kappa 一致性检验）
    ↓
语境情感打分（仅描述性语句）
    ↓
GW 指数 = max(0, 企业环境语调 - 行业年度中位数)
    ↓
动态分位：后 20% → "预警" | 前 80% → "正常"
```

---

## 🚀 快速开始

### 环境要求

| 组件              | 要求                |
| ----------------- | ------------------- |
| **Python**  | 3.10+               |
| **Node.js** | 18+                 |
| **内存**    | 建议 8GB 以上       |
| **磁盘**    | 至少 500MB 可用空间 |

### 方式一：一键启动（Windows）

双击根目录下的 `启动系统.bat`，自动启动后端和前端服务。

### 方式二：手动启动

```bash
# 1. 启动后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. 启动前端（新终端）
cd frontend
npm install
npx vite --host
```

启动后访问：

- **前端页面**：http://localhost:5173
- **后端 API 文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/health

### 初始化种子数据

```bash
cd backend
python scripts/init_db.py      # 创建数据库表
python scripts/seed_data.py     # 导入 10 家示例企业数据
```

---

## 📁 项目结构

```
greenwash_system/
├── 启动系统.bat                  # Windows 一键启动脚本
├── README.md                     # 项目说明
├── .gitignore                    # Git 忽略规则
│
├── backend/                      # 后端服务 (FastAPI)
│   ├── .env.example              # 环境变量模板
│   ├── requirements.txt          # Python 依赖
│   ├── app/
│   │   ├── main.py               # 应用入口 + CORS + 路由
│   │   ├── api/                  # API 路由层
│   │   │   ├── dashboard.py      # 仪表盘接口
│   │   │   ├── companies.py      # 企业查询接口
│   │   │   ├── analysis.py       # 分析接口
│   │   │   └── batch.py          # 批量接口
│   │   ├── core/                 # 核心配置
│   │   │   ├── config.py         # 配置管理
│   │   │   └── database.py       # 数据库连接
│   │   ├── models/               # 数据模型 (SQLAlchemy)
│   │   │   ├── company.py        # 企业信息表
│   │   │   ├── analysis.py       # 分析记录表
│   │   │   ├── sentence.py       # 语句分类表
│   │   │   ├── industry.py       # 行业基准表
│   │   │   └── watchlist.py      # 关注列表表
│   │   ├── schemas/              # Pydantic 请求/响应模型
│   │   └── services/             # 业务服务层
│   │       ├── mock_service.py   # Mock 分析服务
│   │       └── industry_service.py # 行业基准服务
│   └── scripts/
│       ├── init_db.py            # 数据库初始化
│       └── seed_data.py          # 种子数据导入
│
├── frontend/                     # 前端应用 (Vue 3)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js               # 应用入口
│       ├── App.vue               # 根组件
│       ├── api/                  # API 接口层
│       ├── assets/styles/        # 样式文件
│       ├── components/           # 组件
│       │   ├── common/           # 通用组件
│       │   ├── home/             # 首页组件
│       │   └── analyze/          # 分析页组件
│       ├── router/               # 路由配置
│       ├── stores/               # 状态管理 (Pinia)
│       └── views/                # 页面视图
│
├── data/                         # 数据存储
│   ├── db/                       # SQLite 数据库
│   └── output/                   # 输出结果
│
└── docs/                         # 文档
    ├── technical_design.md       # 技术设计文档
    ├── greenwash_demo_v4.html    # 前端原型参考
    ├── （CN）How Environmental Courts...docx  # 参考论文
    └── diagrams/                 # 系统图表
```

---

## 🔧 配置说明

### Mock 模式（默认）

无需任何配置，开箱即用。系统内置 Mock 服务，模拟三模型分析流程，便于演示和测试。

### 真实 LLM 模式

1. 复制 `backend/.env.example` 为 `backend/.env`
2. 填入 API Key：

```env
# 应用配置
APP_NAME=GreenwashGuard
DEBUG=true
FRONTEND_URL=http://localhost:5173
DATABASE_URL=sqlite:///../data/db/greenwash_guard.db

# Mock 模式开关
MOCK_MODE=true

# LLM API Keys（MOCK_MODE=false 时必填）
DEEPSEEK_API_KEY=your_deepseek_api_key
QWEN_API_KEY=your_qwen_api_key
GLM_API_KEY=your_glm_api_key
```

> ⚠️ `.env` 文件已在 `.gitignore` 中排除，不会提交到 Git 仓库。

---

## 🛡️ LLM 调用保护机制

系统针对高并发场景和 API 不稳定情况，实现三层调用保护：

| 机制               | 说明                                                               |
| ------------------ | ------------------------------------------------------------------ |
| **令牌桶限流**     | 控制 LLM API 每秒调用频率，支持突发流量（可配置 QPS 和桶容量）    |
| **熔断降级**       | 连续失败超过阈值自动熔断，超时后进入半开探测，成功则恢复，失败则重新熔断 |
| **指数退避重试**   | 基于错误类型智能判断是否可重试（网络/超时/限流 → 重试，业务错误 → 不重试），带随机抖动避免惊群效应 |

---

## 🧪 单元测试

```bash
cd backend
python -m pytest tests/ -v
```

测试覆盖（81 个用例）：

| 测试文件                      | 覆盖内容                                        |
| ----------------------------- | ----------------------------------------------- |
| `test_mock_service.py`        | Mock 分类准确性、情感打分范围、文本生成、分析流程 |
| `test_fusion_calculator.py`   | 多数投票融合、集成平均、GW 指数计算、文本工具    |
| `test_llm_client.py`          | 令牌桶限流、熔断器状态转换、Mock 客户端、结果解析 |
| `test_logging.py`             | 请求ID追踪、JSON 格式化、LLM 指标收集、日志配置  |
| `test_services.py`            | 服务层集成测试                                  |

---

## 🧪 风险分级规则

| 等级              | 条件                         | 说明             |
| ----------------- | ---------------------------- | ---------------- |
| **正常**    | GW 指数处于全市场前 80% 分位 | 不显示任何标签   |
| **预警** 🔴 | GW 指数处于全市场后 20% 分位 | 显示红色印章标记 |

分位阈值基于当前数据库中的真实分布**动态计算**，不设固定数值，随数据量增长自动调整。

---

## 📚 参考论文

本系统基于以下论文的方法论构建：

> *How Environmental Courts Inhibit Corporate Greenwashing—Evidence from Heterogeneous LLM Measures*

详细技术方案请参见 [docs/technical_design.md](docs/technical_design.md)

---

## 📝 License

© 2024 谛观 GreenwashGuard

---

*如有问题，请参考技术文档或联系开发团队。*
