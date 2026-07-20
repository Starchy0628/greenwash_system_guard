# 谛观 GreenwashGuard — 企业漂绿风险监测平台

基于三异构大语言模型多数投票机制的A股上市公司环境披露"漂绿"风险测算系统。

***

## 快速开始

### 环境要求

- **Python 3.10+**（必需）
- 浏览器：Chrome / Edge / Firefox 最新版
- **Node.js 不需要**（前端已预构建，开箱即用）

### 一键启动（Windows）

**双击** **`启动系统.vbs`**

- 无黑框、无控制台窗口
- 自动检查环境、安装依赖、初始化数据库
- 启动完成后自动打开浏览器
- 访问地址：<http://localhost:8000>

**停止服务：双击** **`停止系统.vbs`**

> 首次启动会自动安装Python依赖，可能需要1-2分钟，请耐心等待。

***

## 技术栈

| 层级   | 技术                                                             |
| ---- | -------------------------------------------------------------- |
| 前端   | Vue 3 + Vite + Pinia + Naive UI + ECharts + Tailwind CSS（已预构建） |
| 后端   | FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Uvicorn（单端口托管前端）      |
| 数据库  | SQLite（默认，零配置）/ PostgreSQL（生产）                                 |
| AI模型 | DeepSeek-R1 + Qwen-Max + GLM-4.7（三模型集成），默认Mock模式无需Key          |

***

## 项目结构

```
greenwashguard/
├── 启动系统.vbs                 # 一键静默启动（推荐）
├── 停止系统.vbs                 # 停止服务
├── launcher.py                  # 启动管理器（VBS调用）
├── README.md                    # 本文档
├── technical_design.md          # 详细技术设计文档
│
├── backend/                     # FastAPI 后端
│   ├── app/
│   │   ├── main.py              # 应用入口（含前端静态文件托管）
│   │   ├── api/                 # API路由层
│   │   │   ├── stream_analysis.py   # SSE流式分析（核心）
│   │   │   ├── pdf_analysis.py      # PDF上传分析
│   │   │   ├── dashboard.py         # 仪表盘接口
│   │   │   ├── companies.py         # 企业查询接口
│   │   │   └── watchlist.py         # 关注列表接口
│   │   ├── core/                # 核心配置（数据库、日志、工具）
│   │   ├── models/              # SQLAlchemy数据模型
│   │   ├── schemas/             # Pydantic数据校验
│   │   └── services/            # 业务逻辑层
│   │       ├── analysis_orchestrator.py  # 分析流程编排+SSE推送
│   │       ├── llm_client.py            # LLM客户端（限流/熔断/重试）
│   │       ├── fusion.py                # 模型融合（多数投票）
│   │       ├── calculator.py            # GW指数计算器
│   │       ├── mock_service.py          # Mock模式（离线演示）
│   │       ├── pdf_parser.py            # PDF解析
│   │       └── cninfo_crawler.py        # 巨潮资讯年报爬虫
│   ├── scripts/                 # 工具脚本
│   ├── data/                    # 行业映射等数据
│   ├── tests/                   # 单元测试
│   ├── requirements.txt         # Python依赖
│   └── .env.example             # 环境变量模板
│
└── frontend/                    # Vue 3 前端
    ├── dist/                    # 预构建产物（直接使用）
    └── src/                     # 源代码（开发者用）
```

***

## 核心概念

| 分类标签                   | 含义                                |
| ---------------------- | --------------------------------- |
| **substantive（实质性陈述）** | 有具体数据支撑的环境信息披露，如"环保投入5000万，减排15%" |
| **descriptive（描述性陈述）** | 空泛口号式表述，如"我们高度重视绿色发展"——**漂绿主要来源** |
| **non\_env（非环保语句）**    | 虽含环保关键词但实际讨论其他内容                  |

**GW漂绿指数** = max(0, 企业描述性语句平均语调 - 同行业年度中位数)

- 数值越高，表示企业越倾向于用空泛口号"漂绿"
- 系统自动将行业内GW指数排名前20%标记为"预警"

***

## 数据流向

```
用户输入股票代码/上传PDF
        ↓
[前端] 建立SSE连接，实时接收进度
        ↓
[后端] 检查数据库缓存 → 有则直接返回
        ↓
[爬虫/PDF解析] 获取年报文本
        ↓
[文本处理] 分句 → 关键词过滤提取环境语句
        ↓
[三模型并行分类] DeepSeek + Qwen + GLM 独立判断（或Mock规则）
        ↓
[多数投票] 三模型投票决定最终分类，计算Kappa一致性
        ↓
[情感打分] 仅对描述性语句打 -1~1 情感分
        ↓
[GW指数计算] 企业语调 - 行业中位数（下限为0）
        ↓
[数据库] 保存结果 → SSE推送给前端
        ↓
[前端] 实时更新UI：进度→结果→图表
```

***

## 环境变量配置

在 `backend/.env` 中配置（首次启动会自动从 `.env.example` 创建）：

| 变量                 | 说明                                      |
| ------------------ | --------------------------------------- |
| `APP_MODE`         | `mock`（默认，无需API Key演示）或 `real`（调用真实LLM） |
| `DATABASE_URL`     | 数据库连接串，默认SQLite零配置                      |
| `DEEPSEEK_API_KEY` | DeepSeek API Key（真实模式需要）                |
| `QWEN_API_KEY`     | 通义千问 API Key（真实模式需要）                    |
| `GLM_API_KEY`      | 智谱 GLM API Key（真实模式需要）                  |
| `MDA_ROOT`         | 本地MD\&A文本目录路径（可选）                       |

***

## 开发者指南

### 手动启动（开发调试）

```bash
# 后端
cd backend
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --reload --port 8000

# 浏览器访问 http://localhost:8000
```

### 前端开发（需要Node.js 18+）

```bash
cd frontend
npm install
npm run dev      # 开发服务器 http://localhost:5173
npm run build    # 重新构建到 dist/
```

### 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

***

## 常见问题

**Q: 双击启动后浏览器没打开？**
A: 请查看 `launcher.log` 日志文件，或手动访问 <http://localhost:8000>

**Q: 提示端口被占用？**
A: 先双击 `停止系统.vbs`，或手动结束python进程后重新启动。

**Q: 需要联网吗？**
A: Mock模式可以离线使用。真实LLM模式需要联网调用三个AI模型的API。

**Q: 文件夹里那些带点的文件/文件夹是什么？**
A:

- `.gitignore` / `.gitattributes`：Git版本控制配置，需要保留
- `.env.example`：环境变量模板，需要保留
- `.env`：本地配置（含密钥），不要分享
- `__pycache__/`：Python缓存，可删除
- `node_modules/`：前端依赖（已预构建dist，不需要）
- `.server.pid`、`launcher.log`：运行时生成，可删除

详细说明请见 [technical\_design.md](technical_design.md)。

***

## 注意事项

- **Mock模式**无需API Key即可体验全流程，使用内置规则模拟LLM判断
- **真实模式**需要三个平台的API Key，注意控制调用量
- 金融类、ST/\*ST/PT公司不在分析范围内

