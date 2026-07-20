============================================================
backend/app/api - API路由层
============================================================

【文件夹作用】
定义所有HTTP REST接口和SSE流式推送端点。

【文件说明】
- stream_analysis.py    【核心】SSE流式分析接口（股票代码分析）
- pdf_analysis.py       PDF上传分析接口（支持上传年报PDF分析）
- dashboard.py          仪表盘数据接口（Top10、分布、地图等汇总数据）
- companies.py          企业查询接口（搜索、详情、历史趋势、语句列表）
- watchlist.py          关注列表接口（添加/删除/查询关注企业）
- analysis.py           普通分析结果查询接口

【接口前缀】
所有接口统一前缀：/api

【主要SSE事件】
- connected    连接建立
- progress     进度更新
- phase        阶段切换
- model_classified 单句分类完成
- complete     分析完成
- error        错误
