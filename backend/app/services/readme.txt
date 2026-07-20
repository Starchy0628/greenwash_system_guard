============================================================
backend/app/services - 业务逻辑层
============================================================

【文件夹作用】
核心业务逻辑实现，包含分析流程编排、LLM调用、分类算法、情感分析、模型融合等所有核心算法。

【文件说明】
- __init__.py               Python包标识
- analysis_orchestrator.py  【核心】分析流程编排器 + SSE进度推送
- llm_client.py             LLM统一客户端（令牌桶限流、熔断器、指数退避重试）
- classifier.py             语句三分类器（substantive/descriptive/non_env）
- sentiment.py              情感分析器（仅对描述性语句打[-1,1]情感分）
- fusion.py                 三模型融合（多数投票分类 + 集成平均情感 + Fleiss' Kappa）
- calculator.py             GW漂绿指数计算器（Winsorize缩尾、语调聚合、行业对比）
- industry_service.py       行业基准服务（动态计算行业中位数、预警阈值80分位）
- mock_service.py           Mock演示模式（关键词规则模拟LLM，无需API Key）
- text_utils.py             文本处理工具（分句、关键词过滤、Winsorize缩尾）
- pdf_parser.py             PDF年报解析（表格转文本、ESG指标提取、章节定位）
- cninfo_crawler.py         巨潮资讯网年报爬虫

【容错机制】
- 令牌桶限流：每模型20 req/min
- 熔断器：连续5次失败打开，30秒后半开试探
- 指数退避重试：2s/4s/8s重试3次
- Mock降级：三模型全部不可用时自动切换Mock模式
