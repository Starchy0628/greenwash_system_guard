"""验证 Mock 分析完整流程"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.mock_service import run_mock_analysis

text = (
    "公司高度重视环境保护工作，全年环保投入达5000万元，同比增长15%。"
    "通过ISO14001认证，碳排放强度降低20%。"
    "我们持续推动绿色低碳转型，实现可持续发展。"
    "公司全年实现营业收入稳步增长。"
)

result = run_mock_analysis(text, "白酒")

print(f"Total sentences: {result['total_sentences']}")
print(f"Env sentences: {result['env_sentences']}")
print(f"Substantive: {result['substantive_count']}")
print(f"Descriptive: {result['descriptive_count']}")
print(f"Tone score: {result['tone_score']}")
print(f"GW Index: {result['gw_index']}")
print(f"Risk level: {result['risk_level']}")
print(f"Fleiss Kappa: {result['fleiss_kappa']}")
print(f"Dispute count: {result['dispute_count']}")
print(f"Unanimous: {result['unanimous_count']}")
print(f"Majority: {result['majority_count']}")
print(f"Divergence: {result['divergence_count']}")
print("Mock analysis pipeline: OK")