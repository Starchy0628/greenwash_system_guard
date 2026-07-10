# 企业漂绿测算系统 — Streamlit 演示应用 实现方案

## 一、Context

基于现有 `greenwash_system` Python 后端（已完整实现年报解析、多LLM分类、情感分析、漂绿指数计算等全流程），构建一个 **Streamlit Web 应用**作为前端演示界面。

**使用场景**：学科竞赛答辩演示，要求部署简单（一键启动）、界面专业整洁、突出"异构LLM集成推理"算法创新点、可视化图表直观。

**现有可复用代码**：
- `main.py` — `GreenwashMeasurementSystem` 类，提供 `measure_from_text()`, `measure_from_file()`, `batch_measure()`, `export_results()`, `get_summary()`
- `config/settings.py` — LLM模型配置、关键词库、Prompt模板
- `index_calculation/greenwash_calculator.py` — `CompanyGreenwashResult` 和 `SentenceLevelResult` 数据结构
- `llm_classification/sentence_classifier.py` — 分类器 + `SentenceClassificationResult`
- `model_fusion/fusion_engine.py` — 投票融合、Fleiss' Kappa
- `data_extraction/report_parser.py` — 支持 PDF/DOCX/TXT 解析

---

## 二、新增文件结构

```
greenwash_system/
├── app.py                    # [新增] Streamlit 主入口
├── web/                      # [新增] Web 应用模块
│   ├── __init__.py
│   ├── components/
│   │   ├── __init__.py
│   │   ├── sidebar.py        # 侧边栏：模式切换、API Key、模型信息
│   │   ├── upload.py         # 上传区：文件上传、文本粘贴、企业信息表单
│   │   ├── results.py        # 结果区：指标卡片、分类统计、语句详情表
│   │   ├── charts.py         # 图表区：所有 Plotly 图表生成函数
│   │   └── pipeline.py       # 算法流水线可视化组件
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── home.py           # 标签页1：系统概览 + 算法创新介绍
│   │   ├── analysis.py       # 标签页2：单企业分析（核心功能）
│   │   ├── batch.py          # 标签页3：批量分析
│   │   └── benchmark.py      # 标签页4：行业基准对比
│   └── utils/
│       ├── __init__.py
│       ├── session.py        # Session State 管理
│       └── formatters.py     # 数据格式化、颜色映射
├── requirements.txt           # [新增] 依赖清单
└── run.py                    # [新增] 启动器（环境检查 + 一键启动）
```

---

## 三、UI 布局设计

### 3.1 整体布局

```
┌──────────────┐  ┌──────────────────────────────────────┐
│   侧边栏     │  │  标题栏：企业漂绿测算系统              │
│              │  │  副标题：基于异构大语言模型集成推理     │
│ [AI模式切换] │  ├──────────────────────────────────────┤
│ Mock/真实    │  │  ┌──────┬──────┬──────┬──────┐      │
│              │  │  │ 概览 │单企业│ 批量 │ 基准 │      │
│ [API Key]    │  │  ├──────┴──────┴──────┴──────┤      │
│  可折叠      │  │  │                            │      │
│              │  │  │   当前标签页内容             │      │
│ [模型信息]   │  │  │                            │      │
│  3个模型卡片 │  │  │                            │      │
│              │  │  │                            │      │
│ [关于]       │  │  │                            │      │
└──────────────┘  └──────────────────────────────────────┘
```

### 3.2 四个标签页

| 标签页 | 名称 | 内容 |
|--------|------|------|
| 1 | 系统概览 | 系统介绍、算法6阶段流水线图（第4阶段金色高亮突出创新点）、快速开始指引 |
| 2 | 单企业分析 | 文件上传/文本粘贴 → 企业信息表单 → 分析按钮 → 图表 + 指标卡片 + 语句详情表 |
| 3 | 批量分析 | 多文件上传 → 批量分析 → 企业对比图表（柱状图 + 散点图） |
| 4 | 行业基准 | 行业箱线图、行业均值柱状图、中位数参考表 |

### 3.3 侧边栏设计

- **AI模式切换**：`st.radio`（Mock模式 / 真实AI模式）
- **API Key配置**：`st.expander` 折叠区，三个密码输入框（DeepSeek / Qwen / GLM），仅真实模式显示
- **模型信息面板**：3个模型卡片，展示架构类型和用途
- **关于**：版本信息

### 3.4 答辩演示模式

侧边栏增加"演示模式"开关，开启后：
- 自动加载预设示例文本
- 所有图表放大字体
- 自动展开折叠区
- 隐藏API Key配置区
- 概览页增加"一键演示"按钮

---

## 四、可视化图表设计（共10个图表，使用 Plotly）

| 编号 | 图表名称 | 类型 | 用途 |
|------|---------|------|------|
| 1 | 分类分布环形图 | Donut Chart | 展示实质性/描述性/非环保三类语句占比 |
| 2 | 模型投票一致性柱状图 | Stacked Bar | 展示一致通过/多数通过/完全分歧数量 |
| 3 | Fleiss' Kappa 仪表盘 | Gauge | 量化展示三个模型间一致性 |
| 4 | 情感得分分布直方图 | Histogram + KDE | 描述性语句情感分的分布 |
| 5 | 三模型情感得分对比 | Scatter | 三个模型对同一语句的评分差异 |
| 6 | 漂绿指数仪表盘 | Gauge | 可视化漂绿指数值 + 颜色分区 |
| 7 | 企业漂绿指数横向柱状图 | Horizontal Bar | 批量分析：多企业对比 |
| 8 | 漂绿指数 vs 描述性比例 | Scatter | 散点图展示相关性 |
| 9 | 行业环境语调箱线图 | Box Plot | 行业分布 + 当前企业标注 |
| 10 | 算法流水线图 | 自定义HTML | 6阶段流程，第4阶段金色高亮 |

### 配色方案

- 主色调：深蓝 `#1B4F72`（学术感）
- 创新点高亮：金色 `#D4A017`
- 实质性：绿色 `#27AE60`
- 描述性（漂绿嫌疑）：橙色 `#E67E22`
- 非环保：灰色 `#95A5A6`

---

## 五、数据流

```
用户上传文件/粘贴文本
       │
       ▼
  report_parser.parse()  ─── 提取纯文本
       │
       ▼
  system.measure_from_text()  ─── 调用现有后端全流程
       │
       ▼
  CompanyGreenwashResult  ─── 存入 st.session_state
       │
       ├── formatters.py  ─── 转为 DataFrame
       │
       ├── charts.py  ─── 生成 Plotly 图表
       │
       └── results.py  ─── 渲染指标卡片 + 表格
```

**Session State 管理**：
- `system_mode`：当前模式（mock/real）
- `api_keys`：API Key 字典
- `system_instance`：`GreenwashMeasurementSystem` 实例（懒加载，模式变化时重建）
- `single_result`：最近一次单企业分析结果
- `batch_results`：批量分析结果列表
- `demo_mode`：是否开启演示模式

---

## 六、技术栈

| 类别 | 技术 | 原因 |
|------|------|------|
| Web框架 | Streamlit >= 1.28 | 纯Python、一键启动、内置文件上传组件 |
| 可视化 | Plotly >= 5.17 | 交互式图表、中文字体支持好、与Streamlit原生集成 |
| 数据处理 | Pandas, NumPy | 图表数据转换 |
| 文档解析 | pdfplumber, python-docx, PyPDF2 | 现有系统已使用 |
| 网络请求 | requests | LLM API调用（现有） |

**运行环境**：Python 3.8+，Windows/macOS/Linux

**启动命令**：
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 七、算法创新点展示策略

在答辩中要突出"**异构LLM集成推理**"这个核心创新：

1. **概览页**：算法流水线图中第4阶段用金色高亮 + 三个模型卡片并排展示架构差异
2. **分析结果页**：模型投票一致性图（图表2）+ Fleiss' Kappa 仪表盘（图表3）直接量化展示创新效果
3. **语句详情表**：展示每条语句被三个模型独立判断的结果，可展开查看原始推理过程
4. **漂绿指数仪表盘**：用颜色分区直观展示漂绿程度

---

## 八、实施步骤

| 步骤 | 内容 | 涉及文件 |
|------|------|---------|
| 1 | 创建 `requirements.txt` 和 `run.py` | requirements.txt, run.py |
| 2 | 创建 `web/utils/session.py` — Session State 管理 | web/utils/session.py |
| 3 | 创建 `web/utils/formatters.py` — 数据格式化 | web/utils/formatters.py |
| 4 | 创建 `web/components/sidebar.py` — 侧边栏 | web/components/sidebar.py |
| 5 | 创建 `web/components/upload.py` — 上传组件 | web/components/upload.py |
| 6 | 创建 `web/components/charts.py` — 10个图表函数 | web/components/charts.py |
| 7 | 创建 `web/components/results.py` — 结果展示 | web/components/results.py |
| 8 | 创建 `web/components/pipeline.py` — 流水线图 | web/components/pipeline.py |
| 9 | 创建 `web/pages/home.py` — 概览页 | web/pages/home.py |
| 10 | 创建 `web/pages/analysis.py` — 单企业分析页 | web/pages/analysis.py |
| 11 | 创建 `web/pages/batch.py` — 批量分析页 | web/pages/batch.py |
| 12 | 创建 `web/pages/benchmark.py` — 行业基准页 | web/pages/benchmark.py |
| 13 | 创建 `app.py` — Streamlit 主入口 | app.py |
| 14 | 端到端测试：启动应用 → 上传文件 → 查看结果 | — |

---

## 九、验证方式

1. 启动应用：`streamlit run app.py`，确认页面正常加载
2. 在Mock模式下，粘贴示例文本，点击"开始分析"，验证：
   - 指标卡片正确显示
   - 10个图表正常渲染
   - 语句详情表数据正确
   - 导出JSON功能正常
3. 批量分析：上传多个文件，验证批量对比图表
4. 切换到真实AI模式，填入API Key，验证切换逻辑
5. 开启演示模式，验证一键演示功能
6. 在大屏（1920x1080）上验证字体大小和布局