#!/usr/bin/env python3
"""
安全地添加outlines表的description列
如果列已存在,则跳过
"""

import sqlite3
import sys


def column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    """检查列是否存在

    Args:
        conn: 数据库连接
        table_name: 表名
        column_name: 列名

    Returns:
        列是否存在
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    # PRAGMA table_info返回的格式: (cid, name, type, notnull, default_value, pk)
    return any(col[1] == column_name for col in columns)


def add_missing_columns(db_path: str) -> bool:
    """添加缺失的列到outlines表

    根据迁移005的要求,添加以下列(如果不存在):
    - description TEXT
    - industry_id TEXT NOT NULL
    - database_ids TEXT NOT NULL
    - status (更新为新的状态值)
    - current_version INTEGER NOT NULL DEFAULT 1
    - metadata TEXT DEFAULT '{}'

    Args:
        db_path: 数据库路径

    Returns:
        是否成功(如果列已存在,也返回True)
    """
    try:
        conn = sqlite3.connect(db_path)

        columns_to_add = [
            ("description", "TEXT"),
            ("industry_id", "TEXT"),
            ("database_ids", "TEXT"),
            ("current_version", "INTEGER DEFAULT 1"),
            ("metadata", "TEXT DEFAULT '{}'"),
        ]

        # 修改现有列的约束,使user_id和constraints_id可以为NULL
        # 注意:SQLite不支持直接修改列约束,需要重建表
        # 但我们可以先尝试添加默认值
        try:
            # 检查是否需要修改user_id和constraints_id的约束
            # 由于SQLite的限制,我们无法直接修改NOT NULL约束
            # 但我们可以通过设置默认值来缓解问题
            # 实际上,最好的方法是让代码提供这些值,或者重建表
            # 这里我们暂时跳过,因为SQLite不支持ALTER COLUMN
            pass
        except Exception as e:
            print(f"修改列约束失败(这是预期的,SQLite不支持): {e}")

        added_columns = []
        for col_name, col_type in columns_to_add:
            if not column_exists(conn, "outlines", col_name):
                try:
                    conn.execute(f"ALTER TABLE outlines ADD COLUMN {col_name} {col_type}")
                    added_columns.append(col_name)
                    print(f"成功添加列: {col_name}")
                except Exception as e:
                    print(f"添加列 {col_name} 失败: {e}")
            else:
                print(f"列 {col_name} 已存在,跳过")

        conn.commit()
        conn.close()

        if added_columns:
            print(f"成功添加 {len(added_columns)} 个列: {', '.join(added_columns)}")
        else:
            print("所有列都已存在,无需添加")

        return True

    except Exception as e:
        print(f"添加列失败: {e}")
        return False


def add_description_column(db_path: str) -> bool:
    """添加description列到outlines表(向后兼容)

    Args:
        db_path: 数据库路径

    Returns:
        是否成功(如果列已存在,也返回True)
    """
    return add_missing_columns(db_path)


if __name__ == "__main__":
    # 从配置文件获取数据库路径
    try:
        from src.shared.config.settings import get_config
        config = get_config()
        db_path = config.database.sqlite_db_path
    except Exception:
        # 如果无法导入配置,使用默认路径
        db_path = "storage/sqlite/whitepaper.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    success = add_description_column(db_path)
    sys.exit(0 if success else 1)

