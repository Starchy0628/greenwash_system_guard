# 谛观 GreenwashGuard — 企业漂绿风险智能监测平台

基于三异构大语言模型多数投票机制的A股上市公司环境披露"漂绿"风险测算系统。

> 参考论文：*How Environmental Courts Inhibit Corporate Greenwashing—Evidence from Heterogeneous LLM Measures*

---

## 快速开始

### 环境要求

- **Python 3.10+**（必需）
- 浏览器：Chrome / Edge / Firefox 最新版
- **Node.js 不需要**（前端已预构建，开箱即用）

### 一键启动（Windows）

**双击 `启动系统.vbs`**

- 无黑框、无控制台窗口，完全静默后台启动
- 自动检查环境、安装依赖、初始化数据库
- 启动完成后自动打开浏览器
- 访问地址：http://localhost:8000

**停止服务：双击 `停止系统.vbs`**

> 首次启动会自动安装Python依赖，可能需要1-2分钟，请耐心等待。如有问题查看 `launcher.log`。

---

## 核心功能

| 功能 | 说明 |
|------|------|
| 股票代码分析 | 输入A股股票代码，自动分析年报MD&A中的漂绿风险 |
| PDF上传分析 | 拖拽上传年报/ESG报告PDF，本地解析不上传 |
| SSE实时进度 | 分析过程实时推送，逐句显示模型分类结果 |
| GW漂绿指数 | 企业语调相对行业基准的正向偏离，数值越高漂绿风险越大 |
| 三模型投票 | DeepSeek-R1 + Qwen-Max + GLM-4.7 独立判断后多数投票 |
| 中国风险地图 | ECharts中国地图，按省份展示企业漂绿风险分布 |
| Top10高风险 | GW指数排名前十的企业卡片展示 |
| 语句级追溯 | 查看每句话的三模型原始分类、投票结果、情感分 |
| 关注列表 | 本地持久化关注企业，随时查看 |
| Mock离线模式 | 默认开启，无需API Key即可体验完整流程 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Pinia + Naive UI + ECharts + Tailwind CSS（预构建） |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Uvicorn（单端口托管前端） |
| 数据库 | SQLite（默认，零配置）/ PostgreSQL（生产） |
| AI模型 | DeepSeek-R1 + Qwen-Max + GLM-4.7（三模型集成投票），默认Mock模式 |

---

## 技术文档

详细的技术路线、算法设计、实验结果、部署说明请参阅 [技术文档.md](技术文档.md)，包含：

1. 项目概述与解题思路
2. 系统架构与技术栈选型
3. 核心算法与关键技术细节（多数投票、GW指数、Prompt工程、容错机制）
4. 数据来源合法性声明
5. 技术攻关脉络（6大难点与解决方案）
6. 实验设计与量化指标（准确率91%、Fleiss' κ=0.82、区分效度检验）
7. 数据模型与API接口
8. 前端架构与部署指南
9. 文件结构说明

---

## 项目结构

```
greenwashguard/
├── 启动系统.vbs          一键静默启动（推荐）
├── 停止系统.vbs          停止后台服务
├── 启动系统.bat          开发者调试启动（显示控制台）
├── launcher.py           Python启动管理器
├── README.md             本文档
├── 技术文档.md            详细技术设计文档
│
├── backend/              FastAPI后端
│   ├── app/              应用代码（API、服务、模型、配置）
│   ├── scripts/          工具脚本（初始化、种子数据）
│   ├── tests/            单元测试
│   ├── data/             行业分类数据
│   └── requirements.txt  Python依赖
│
└── frontend/             Vue 3前端
    ├── dist/             预构建产物（直接使用）
    └── src/              源代码（开发者用）
```

---

## 开发者指南

### 手动启动（调试）

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --reload --port 8000
# 浏览器访问 http://localhost:8000
```

### 前端开发（需Node.js 18+）

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

### 环境变量

在 `backend/.env` 中配置（首次启动自动从`.env.example`创建）：

- `APP_MODE=mock`（默认）：离线演示，无需API Key
- `APP_MODE=real`：调用真实LLM，需配置 `DEEPSEEK_API_KEY`、`QWEN_API_KEY`、`GLM_API_KEY`

---

## 常见问题

**Q: 双击启动后浏览器没打开？**
A: 查看 `launcher.log`，或手动访问 http://localhost:8000

**Q: 提示端口被占用？**
A: 先双击`停止系统.vbs`，或在任务管理器中结束python进程后重新启动。

**Q: 需要联网吗？**
A: Mock模式完全离线可用。真实LLM模式需要联网调用API。

**Q: 测试文件要删掉吗？**
A: 不需要。`backend/tests/`是单元测试代码，展示工程质量；`backend/scripts/`中只保留了必要的初始化脚本，临时测试脚本已清理。

---

## 注意事项

- 默认Mock模式无需API Key，使用关键词规则模拟LLM判断
- 真实模式需配置三个平台API Key，注意控制调用量
- 金融类、ST/*ST/PT公司按论文方法论剔除在分析范围外
- PDF上传仅在本地解析，不上传至第三方服务器
- 每个子文件夹均有`readme.txt`说明文件用途（参赛要求）
