============================================================
frontend - 前端Web界面目录
============================================================

【文件夹作用】
Vue 3前端应用，提供用户交互界面，包括企业搜索、PDF上传、结果可视化、仪表盘等功能。

【技术栈】
- Vue 3 + Vite
- Pinia（状态管理）
- Naive UI（组件库）
- ECharts（图表可视化）
- Tailwind CSS（样式框架）
- Axios（HTTP请求）

【子文件夹说明】
- src/           源代码目录
  - api/         API请求封装（Axios实例、接口定义）
  - assets/      静态资源（图片、样式、GeoJSON地图数据）
  - components/  Vue组件（所有UI组件）
  - composables/ 组合式函数（可复用逻辑）
  - stores/      Pinia状态管理
  - App.vue      根组件
  - main.js      应用入口
- dist/          生产构建产物（已编译，可直接部署）
- public/        公共静态资源
- node_modules/  npm依赖包（不提交版本控制）
- package.json   npm依赖声明和脚本
- vite.config.js Vite构建配置
- tailwind.config.js Tailwind CSS配置
- index.html     HTML入口模板

【开发命令】
npm install       安装依赖
npm run dev       启动开发服务器（http://localhost:5173）
npm run build     构建生产版本（输出到dist/）
npm run preview   预览生产构建
