"""数据库初始化脚本"""
import sys
from pathlib import Path

# 确保 backend/ 目录在 Python 路径中
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.database import init_db, engine

if __name__ == "__main__":
    print("初始化数据库表...")
    init_db()
    print("数据库表创建完成！")