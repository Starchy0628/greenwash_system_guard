============================================================
backend/scripts - 工具脚本目录
============================================================

【文件夹作用】
存放数据库初始化、数据导入、批量处理、测试等运维工具脚本。

【主要文件说明】
- init_db.py                  初始化数据库表结构
- seed_data.py                导入种子演示数据（Top10示例企业）
- batch_pipeline.py           批量分析流水线（批量处理多家企业）
- import_real_mda_sentences.py  导入真实CMDA管理层讨论与分析数据
- import_cmda_mock.py         导入CMDA Mock数据
- recalculate_medians.py      重新计算行业年度语调中位数基准
- recalc_benchmarks.py        重算行业基准
- build_industry_map.py       构建行业分类映射
- update_industry*.py         更新行业分类相关脚本
- clean_duplicate_records.py  清理数据库重复记录
- remove_financial_companies.py  剔除金融类公司
- test_*.py                   各类测试脚本
