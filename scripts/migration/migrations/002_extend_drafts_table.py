"""
扩展草稿表的迁移脚本

添加新字段以支持草稿服务的数据库存储功能.
"""

import sqlite3

from src.infrastructure.storage.sqlite.connection import get_connection_manager
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


def migrate():
    """执行迁移"""
    connection_manager = get_connection_manager()
    conn = connection_manager.get_connection()

    try:
        cursor = conn.cursor()

        # 检查并添加新字段
        new_columns = [
            ("sections", "TEXT", "DEFAULT '[]'"),
            ("versions", "TEXT", "DEFAULT '[]'"),
            ("database_ids", "TEXT", "DEFAULT '[]'"),
            ("industry_id", "TEXT", ""),
            ("description", "TEXT", ""),
            ("current_version", "INTEGER", "DEFAULT 1"),
            ("metadata", "TEXT", "DEFAULT '{}'"),
        ]

        # 获取现有列
        cursor.execute("PRAGMA table_info(drafts)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # 添加不存在的列
        for column_name, column_type, default in new_columns:
            if column_name not in existing_columns:
                try:
                    alter_sql = f"ALTER TABLE drafts ADD COLUMN {column_name} {column_type} {default}"
                    cursor.execute(alter_sql)
                    logger.info("添加列: %s", column_name)
                except sqlite3.OperationalError as e:
                    logger.warning("添加列失败(可能已存在): %s, 错误: %s", column_name, e)

        conn.commit()
        logger.info("草稿表扩展迁移完成")

    except Exception as e:
        conn.rollback()
        logger.error("迁移失败: %s", e, exc_info=True)
        raise
    finally:
        connection_manager.close_connection(conn)


if __name__ == "__main__":
    migrate()

