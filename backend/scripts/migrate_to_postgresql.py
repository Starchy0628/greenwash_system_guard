"""
SQLite → PostgreSQL 数据迁移脚本

用法:
    python scripts/migrate_to_postgresql.py

前提:
    1. PostgreSQL 已启动（默认端口 15432）
    2. 数据库 greenwash_guard 已创建
    3. psycopg2-binary 已安装

迁移内容:
    - companies 表（企业基础信息）
    - analysis_records 表（分析记录）
    - sentences 表（语句分析结果）
    - industry_benchmarks 表（行业基准）
    - watchlist 表（监控列表）
"""
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import create_engine, text, inspect, MetaData, Table
from sqlalchemy.orm import sessionmaker
from app.core.database import SessionLocal, init_db, Base
from app.core.config import get_settings
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.models.industry import IndustryBenchmark
from app.models.watchlist import Watchlist

settings = get_settings()

# ============================================================
#  配置
# ============================================================
PG_URL = "postgresql://postgres:postgres@localhost:15432/greenwash_guard"
SQLITE_PATH = BASE_DIR.parent / "data" / "db" / "greenwash_guard.db"
SQLITE_URL = f"sqlite:///{SQLITE_PATH}"

# 需要迁移的表（按依赖顺序）
TABLE_ORDER = ["companies", "industry_benchmarks", "analysis_records", "sentences", "watchlist"]

# 布尔列名（SQLite 存 0/1，PostgreSQL 需要 True/False）
# 注意: used_seed_data 在 SQLAlchemy 定义为 Integer 类型，不需要转换
BOOLEAN_COLUMNS = {
    "companies": ["is_a_share", "is_active", "is_seed", "is_st"],
    "analysis_records": ["is_latest"],
    "sentences": ["needs_review"],
    "watchlist": ["is_active"],
}


def count_rows(engine, table_name: str) -> int:
    """统计表中行数"""
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar()


def migrate_table(sq_engine, pg_engine, table_name: str):
    """逐表迁移数据"""
    print(f"\n  📦 迁移 {table_name}...")
    
    # 获取源表数据
    with sq_engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table_name}"))
        rows = [dict(row._mapping) for row in result]
        columns = list(rows[0].keys()) if rows else []
    
    print(f"     读取 {len(rows)} 行")
    
    if not rows:
        return
    
    # 布尔列转换：SQLite 的 0/1 → PostgreSQL 的 True/False
    bool_cols = BOOLEAN_COLUMNS.get(table_name, [])
    for row in rows:
        for col in bool_cols:
            if col in row:
                row[col] = bool(row[col])
    
    # 插入到目标表（禁用外键检查以兼容跨表迁移）
    with pg_engine.connect() as conn:
        # 禁用外键约束检查
        conn.execute(text("SET session_replication_role = 'replica'"))
        conn.commit()
        
        for row in rows:
            placeholders = ", ".join([f":{col}" for col in columns])
            cols = ", ".join(columns)
            conn.execute(
                text(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"),
                row,
            )
        conn.commit()
        
        # 恢复外键约束检查
        conn.execute(text("SET session_replication_role = 'origin'"))
        conn.commit()
    
    pg_count = count_rows(pg_engine, table_name)
    print(f"     PostgreSQL 现在有 {pg_count} 行")


def main():
    print("=" * 60)
    print("  SQLite → PostgreSQL 数据迁移")
    print("=" * 60)
    
    # 1. 检查 SQLite 数据库
    if not SQLITE_PATH.exists():
        print(f"\n❌ SQLite 数据库不存在: {SQLITE_PATH}")
        print("   请先运行 init_db.py 和 import_companies.py")
        return
    
    print(f"\n📂 SQLite: {SQLITE_PATH}")
    print(f"📂 PostgreSQL: {PG_URL}")
    
    # 2. 创建引擎
    sq_engine = create_engine(SQLITE_URL)
    sq_engine.connect_args = {"check_same_thread": False}
    
    pg_engine = create_engine(
        PG_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    
    # 3. 在 PostgreSQL 中创建表结构
    print("\n🔧 在 PostgreSQL 中创建表结构...")
    Base.metadata.create_all(bind=pg_engine)
    print("   ✅ 表结构创建完成")
    
    # 4. 统计源数据
    print("\n📊 SQLite 源数据统计:")
    for table in TABLE_ORDER:
        try:
            cnt = count_rows(sq_engine, table)
            print(f"   {table}: {cnt} 行")
        except Exception as e:
            print(f"   {table}: 跳过 ({e})")
    
    # 5. 逐表迁移
    print("\n🔄 开始迁移...")
    for table in TABLE_ORDER:
        try:
            migrate_table(sq_engine, pg_engine, table)
        except Exception as e:
            print(f"   ⚠️  迁移 {table} 失败: {e}")
    
    # 6. 验证
    print("\n✅ 验证 PostgreSQL 数据:")
    for table in TABLE_ORDER:
        try:
            cnt = count_rows(pg_engine, table)
            print(f"   {table}: {cnt} 行")
        except Exception as e:
            print(f"   {table}: 跳过 ({e})")
    
    # 7. 更新序列
    print("\n🔧 更新自增序列...")
    with pg_engine.connect() as conn:
        for table in TABLE_ORDER:
            try:
                conn.execute(text(
                    f"SELECT setval('{table}_id_seq', (SELECT COALESCE(MAX(id), 1) FROM {table}))"
                ))
                conn.commit()
            except Exception:
                pass
    print("   ✅ 序列已更新")
    
    print("\n" + "=" * 60)
    print("  🎉 迁移完成！")
    print("=" * 60)
    print(f"""
  下一步:
  1. 修改 .env 中的 DATABASE_URL:
     DATABASE_URL={PG_URL}
  2. 重启后端服务
  3. 验证功能正常
    """)


if __name__ == "__main__":
    main()