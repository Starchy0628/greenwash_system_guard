============================================================
backend/app/core - 核心配置层
============================================================

【文件夹作用】
提供应用的基础设施配置，包括配置管理、数据库连接、日志系统、通用工具函数。

【文件说明】
- __init__.py        Python包标识
- config.py          Pydantic Settings配置管理（读取.env环境变量）
- database.py        SQLAlchemy数据库引擎和Session创建
- logging_setup.py   结构化JSON日志配置
- utils.py           通用工具函数（SSE格式化、请求ID生成等）
