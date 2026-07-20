============================================================
backend/app/models - 数据模型层
============================================================

【文件夹作用】
SQLAlchemy ORM模型定义，对应数据库中的表结构。

【文件说明】
- __init__.py    Python包标识，统一导出所有模型
- company.py     企业表模型（股票代码、名称、行业、是否ST等）
- analysis.py    分析记录表模型（GW指数、语调、风险等级、Kappa一致性等）
- sentence.py    语句级结果表模型（单句分类、情感分数、投票结果等）
- industry.py    行业基准表模型（行业年度语调中位数、预警阈值等）
- watchlist.py   关注列表模型（用户关注的股票）

【表关系】
Company 1:N AnalysisRecord 1:N Sentence
Company 1:N IndustryBenchmark
