#!/usr/bin/env python
"""REAL → NUMERIC/INTEGER/BIGINT マイグレーション

既存PostgreSQLテーブルのREAL列を精度保証型に変更する。
- REAL → NUMERIC(p,s): オッズ、タイム、ハロン、斤量
- REAL → INTEGER: 馬体重、増減差
- REAL → BIGINT: 賞金

追加修正:
- AtoFutan, MaeFutan, RecTime, RecUmaFutan1: 既存データが÷10されていないので÷10適用

Usage:
    python scripts/migrate_real_to_numeric.py [--dry-run]
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# テーブルごとの変更定義: (column, new_type, divide_by_10)
MIGRATIONS = {
    "NL_JC": [
        ("AtoFutan", "NUMERIC(4,1)", True),
        ("MaeFutan", "NUMERIC(4,1)", True),
    ],
    "NL_RA": [
        ("Haron3F", "NUMERIC(4,1)", False),
        ("Haron4F", "NUMERIC(4,1)", False),
        ("Haron3L", "NUMERIC(4,1)", False),
        ("Haron4L", "NUMERIC(4,1)", False),
    ],
    "NL_RC": [
        ("RecTime", "NUMERIC(5,1)", True),
        ("RecUmaFutan1", "NUMERIC(4,1)", True),
    ],
    "NL_SE": [
        ("Futan", "NUMERIC(4,1)", False),
        ("FutanBefore", "NUMERIC(4,1)", False),
        ("BaTaijyu", "INTEGER", False),
        ("ZogenSa", "INTEGER", False),
        ("Time", "NUMERIC(5,1)", False),
        ("Honsyokin", "BIGINT", False),
        ("Fukasyokin", "BIGINT", False),
        ("HaronTimeL4", "NUMERIC(4,1)", False),
        ("HaronTimeL3", "NUMERIC(4,1)", False),
        ("TimeDiff", "NUMERIC(5,1)", False),
        ("DMTime", "NUMERIC(6,1)", False),
        ("DMGosaP", "NUMERIC(5,1)", False),
        ("DMGosaM", "NUMERIC(5,1)", False),
    ],
    "NL_SN": [
        ("Futan", "NUMERIC(4,1)", False),
    ],
    "NL_UM": [
        ("RuikeiHonsyoHeiti", "BIGINT", False),
        ("RuikeiHonsyoSyogai", "BIGINT", False),
        ("RuikeiFukaHeichi", "BIGINT", False),
        ("RuikeiFukaSyogai", "BIGINT", False),
        ("RuikeiSyutokuHeichi", "BIGINT", False),
        ("RuikeiSyutokuSyogai", "BIGINT", False),
    ],
    "NL_SLOP": [
        ("HaronTime4Total", "NUMERIC(5,1)", False),
        ("LapTime_800M_600M", "NUMERIC(4,1)", False),
        ("HaronTime3Total", "NUMERIC(5,1)", False),
        ("LapTime_600M_400M", "NUMERIC(4,1)", False),
        ("HaronTime2Total", "NUMERIC(5,1)", False),
        ("LapTime_400M_200M", "NUMERIC(4,1)", False),
        ("LapTime_200M_0M", "NUMERIC(4,1)", False),
    ],
    "NL_WC": [
        ("HaronTime10Total", "NUMERIC(5,1)", False),
        ("LapTime_2000M_1800M", "NUMERIC(4,1)", False),
        ("HaronTime9Total", "NUMERIC(5,1)", False),
        ("LapTime_1800M_1600M", "NUMERIC(4,1)", False),
        ("HaronTime8Total", "NUMERIC(5,1)", False),
        ("LapTime_1600M_1400M", "NUMERIC(4,1)", False),
        ("HaronTime7Total", "NUMERIC(5,1)", False),
        ("LapTime_1400M_1200M", "NUMERIC(4,1)", False),
        ("HaronTime6Total", "NUMERIC(5,1)", False),
        ("LapTime_1200M_1000M", "NUMERIC(4,1)", False),
        ("HaronTime5Total", "NUMERIC(5,1)", False),
        ("LapTime_1000M_800M", "NUMERIC(4,1)", False),
        ("HaronTime4Total", "NUMERIC(5,1)", False),
        ("LapTime_800M_600M", "NUMERIC(4,1)", False),
        ("HaronTime3Total", "NUMERIC(5,1)", False),
        ("LapTime_600M_400M", "NUMERIC(4,1)", False),
        ("HaronTime2Total", "NUMERIC(5,1)", False),
        ("LapTime_400M_200M", "NUMERIC(4,1)", False),
        ("LapTime_200M_0M", "NUMERIC(4,1)", False),
    ],
}

# RT_テーブルはNL_と同じ構造
RT_MIRRORS = {
    "RT_JC": "NL_JC",
    "RT_RA": "NL_RA",
    "RT_SE": "NL_SE",
}

for rt_table, nl_table in RT_MIRRORS.items():
    if nl_table in MIGRATIONS:
        MIGRATIONS[rt_table] = MIGRATIONS[nl_table]


def generate_sql(dry_run=False):
    """マイグレーションSQLを生成・実行"""
    statements = []

    for table, columns in sorted(MIGRATIONS.items()):
        for col, new_type, needs_divide in columns:
            if needs_divide:
                # まず÷10してからtype変更
                statements.append(
                    f"UPDATE {table} SET {col} = {col} / 10.0 "
                    f"WHERE {col} IS NOT NULL;"
                )
            # ALTER TABLE ... ALTER COLUMN ... TYPE ... USING
            statements.append(
                f"ALTER TABLE {table} ALTER COLUMN {col} "
                f"TYPE {new_type} USING {col}::{new_type};"
            )

    return statements


def main():
    dry_run = "--dry-run" in sys.argv

    statements = generate_sql(dry_run)

    if dry_run:
        print("-- DRY RUN: 以下のSQLが実行されます")
        print()
        for stmt in statements:
            print(stmt)
        print(f"\n-- 合計 {len(statements)} ステートメント")
        return

    # DB接続
    try:
        # ~/jra/db_config.py から取得を試みる
        jra_path = os.path.expanduser("~/jra")
        sys.path.insert(0, jra_path)
        from db_config import DB_PARAMS
        import pg8000
    except ImportError:
        print("ERROR: pg8000 or db_config not found.")
        print("Run with --dry-run to see SQL statements.")
        sys.exit(1)

    conn = pg8000.connect(**DB_PARAMS)
    conn.autocommit = True
    cur = conn.cursor()

    total = len(statements)
    errors = []

    for i, stmt in enumerate(statements, 1):
        try:
            print(f"  [{i}/{total}] {stmt[:80]}...")
            cur.execute(stmt)
        except Exception as e:
            err_msg = str(e)
            # テーブルが存在しない場合はスキップ
            if "does not exist" in err_msg or "UndefinedTable" in err_msg:
                print(f"    SKIP (table not found)")
            elif "UndefinedColumn" in err_msg:
                print(f"    SKIP (column not found)")
            else:
                print(f"    ERROR: {err_msg}")
                errors.append((stmt, err_msg))

    cur.close()
    conn.close()

    print(f"\n完了: {total} ステートメント実行, {len(errors)} エラー")
    if errors:
        print("\nエラー一覧:")
        for stmt, err in errors:
            print(f"  {stmt}")
            print(f"    → {err}")


if __name__ == "__main__":
    main()
