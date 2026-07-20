============================================================
backend/tests - 单元测试目录
============================================================

【文件夹作用】
存放pytest单元测试用例，覆盖核心算法和服务模块。

【文件说明】
- test_fusion_calculator.py    模型融合算法测试（多数投票、Kappa计算）
- test_llm_client.py           LLM客户端测试（限流、熔断、重试）
- test_logging.py              日志系统测试
- test_mock_service.py         Mock服务测试（确定性验证）
- test_services.py             核心服务集成测试

【运行测试】
cd backend
python -m pytest tests/ -v
