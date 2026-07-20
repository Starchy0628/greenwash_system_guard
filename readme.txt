============================================================
谛观 GreenwashGuard - 企业漂绿风险智能监测系统
============================================================

【文件夹作用】
项目根目录，包含整个参赛作品的所有文件。

【文件/子文件夹说明】
- backend/          后端服务代码（FastAPI）
- frontend/         前端界面代码（Vue 3）
- data/             数据目录（CMDA管理层讨论与分析数据集）
- docs/             项目文档目录
- 启动系统.bat       Windows一键启动脚本
- README.md         项目说明文档（快速启动指南）
- 项目参赛要求达标评估报告.md  参赛要求自查评估报告
- 数据来源说明.txt   CNRDS数据来源版权声明

【启动方式】
Windows环境下双击"启动系统.bat"即可一键启动前后端服务。
或手动启动：
1. 后端：cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --port 8000
2. 前端：cd frontend && npm install && npm run dev
3. 访问：http://localhost:5173

【注意事项】
- 默认使用Mock模式，无需API Key即可体验完整功能
- 真实模式需要配置DeepSeek、Qwen、GLM三个大模型的API Key
