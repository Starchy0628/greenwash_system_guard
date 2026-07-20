============================================================
backend - 后端服务目录
============================================================

【文件夹作用】
FastAPI后端服务，提供API接口、业务逻辑处理、数据库操作、LLM调用等核心功能。

【子文件夹说明】
- app/          应用主代码目录
  - api/        API路由层（HTTP接口、SSE流式推送）
  - core/       核心配置（数据库连接、配置管理、日志、工具函数）
  - models/     SQLAlchemy数据模型（ORM）
  - schemas/    Pydantic数据校验模型
  - services/   业务逻辑层（核心算法、LLM客户端、分类器等）
  - main.py     FastAPI应用入口
- data/         静态数据文件（股票列表、行业映射等）
- scripts/      工具脚本（数据库初始化、数据导入、批量分析等）
- tests/        单元测试
- requirements.txt   Python依赖声明
- .env.example       环境变量模板
- .env               本地环境配置（不提交Git）

【启动命令】
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

【API文档】
启动后访问 http://localhost:8000/docs 查看Swagger文档
