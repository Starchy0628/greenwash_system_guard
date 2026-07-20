============================================================
frontend/ - Vue 3前端界面
============================================================

【文件夹作用】
前端用户界面，基于Vue 3 + Vite + Naive UI + ECharts构建。
dist/目录包含预构建产物，后端会自动挂载，无需Node.js即可运行。

【子文件夹说明】
- dist/          预构建产物（已编译，直接由后端托管）
- src/           前端源代码（组件、状态管理、API请求）
- node_modules/  npm依赖包（不提交，npm install生成）

【关键文件】
- package.json        npm依赖与构建脚本
- vite.config.js      Vite构建配置（含开发时代理到8000端口）
- tailwind.config.js  Tailwind CSS配置
- index.html          HTML入口

【开发者注意】
仅修改前端代码时需要Node.js 18+：
npm install    # 安装依赖
npm run dev    # 开发服务器 http://localhost:5173
npm run build  # 构建到dist/
