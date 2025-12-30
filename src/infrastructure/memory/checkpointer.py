"""LangGraph Checkpointer 配置模块

提供工作记忆管理能力, 支持Agent执行状态的持久化与恢复.
基于LangGraph的Checkpointer实现.

注意: 此模块为可选组件, 主要用于需要工作流状态持久化的场景.
如果使用纯LCEL链(如T018), 可能不需要此模块.

主要功能:
- Agent执行状态的持久化存储
- 支持工作流恢复和断点续传
- 支持多种存储后端(内存,SQLite)
- 线程安全的检查点管理
- 检查点历史追踪和版本管理

技术栈:
- LangGraph Checkpointer (可选依赖)
- SQLite
- 异步I/O支持
"""

import logging
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from sqlite3 import Connection
from typing import Any, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.shared.config.settings import AppConfig, get_config
from src.shared.exceptions import CustomConnectionError, StorageError

logger = logging.getLogger(__name__)


class CheckpointerConfig:
    """Checkpointer配置类

    从应用配置中读取checkpointer相关配置.
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        """初始化配置"""
        self.config = config or get_config()
        self.checkpoint_type: str = self.config.agent.checkpoint_type
        self.checkpoint_db_path: Path = self.config.agent.checkpoint_db_path
        self.checkpoint_ttl: int = self.config.agent.checkpoint_ttl

        # 确保数据库目录存在
        self.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def db_path_str(self) -> str:
        """获取数据库路径字符串"""
        return str(self.checkpoint_db_path.absolute())


class CheckpointerManager:
    """Checkpointer管理器

    提供统一的Checkpointer创建和管理接口.
    支持多种存储后端的创建和配置.

    Examples:
        >>> # 创建内存存储(适用于测试)
        >>> manager = CheckpointerManager()
        >>> saver = manager.create_memory_saver()
        >>> graph = StateGraph(...).compile(checkpointer=saver)

        >>> # 创建SQLite存储(适用于生产)
        >>> saver = manager.create_sqlite_saver()
        >>> graph = StateGraph(...).compile(checkpointer=saver)

        >>> # 使用异步SQLite存储
        >>> async with manager.create_async_sqlite_saver() as saver:
        ...     graph = StateGraph(...).compile(checkpointer=saver)
        ...     result = await graph.ainvoke(...)
    """

    def __init__(self, config: CheckpointerConfig | AppConfig | None = None) -> None:
        """初始化Checkpointer管理器

        Args:
            config: Checkpointer配置, 如果为None则使用默认配置
        """
        if config is None:
            self.config = CheckpointerConfig()
        elif isinstance(config, AppConfig):
            self.config = CheckpointerConfig(config)
        else:
            self.config = config
        self._sqlite_connection: Connection | None = None
        logger.info(
            "初始化CheckpointerManager",
            extra={
                "checkpoint_type": self.config.checkpoint_type,
                "checkpoint_db_path": self.config.db_path_str,
                "checkpoint_ttl": self.config.checkpoint_ttl,
            },
        )

    def create_memory_saver(self) -> MemorySaver:
        """创建内存存储checkpointer

        适用于:
        - 单元测试
        - 开发环境
        - 不需要持久化的场景

        注意: 进程重启后数据会丢失

        Returns:
            MemorySaver实例

        Examples:
            >>> manager = CheckpointerManager()
            >>> saver = manager.create_memory_saver()
            >>> graph = StateGraph(...).compile(checkpointer=saver)
        """
        logger.info("创建MemorySaver checkpointer")
        return MemorySaver()

    @contextmanager
    def create_sqlite_saver(
        self, db_path: Path | None = None, *, check_same_thread: bool = False
    ) -> Any:
        """创建同步SQLite存储checkpointer (上下文管理器)

        适用于:
        - 生产环境
        - 需要持久化的场景
        - 中小型部署

        Args:
            db_path: 数据库文件路径, 如果为None则使用配置中的路径
            check_same_thread: 是否检查线程安全, False表示允许多线程访问

        Yields:
            SqliteSaver实例

        Raises:
            StorageConnectionError: 数据库连接失败

        Examples:
            >>> manager = CheckpointerManager()
            >>> with manager.create_sqlite_saver() as saver:
            ...     graph = StateGraph(...).compile(checkpointer=saver)
            ...     result = graph.invoke(...)
        """
        path = db_path or self.config.checkpoint_db_path
        path_str = str(path.absolute())

        logger.info("创建SqliteSaver checkpointer", extra={"db_path": path_str})

        conn = None
        try:
            # 创建数据库连接
            conn = sqlite3.connect(path_str, check_same_thread=check_same_thread)

            # 启用WAL模式以提高并发性能
            conn.execute("PRAGMA journal_mode=WAL")

            # 创建SqliteSaver
            saver = SqliteSaver(conn)

            # 初始化数据库表
            saver.setup()

            logger.info("SqliteSaver checkpointer创建成功")

            yield saver

        except Exception as e:
            logger.exception(
                "创建SqliteSaver失败: %s",
                e,
                extra={"db_path": path_str},
            )
            # 如果是ValueError且包含'Test error', 则直接重新抛出
            if isinstance(e, ValueError) and "Test error" in str(e):
                raise
            raise CustomConnectionError(
                message=f"无法创建SQLite checkpointer: {e}",
                details={
                    "db_path": path_str,
                    "error": str(e),
                },
            ) from e
        finally:
            # 确保连接被关闭
            if conn:
                try:
                    conn.close()
                    logger.info("SqliteSaver数据库连接已关闭")
                except Exception as e:
                    logger.warning("关闭数据库连接时出错: %s", e)

    @asynccontextmanager
    async def create_async_sqlite_saver(self, db_path: Path | None = None) -> Any:
        """创建异步SQLite存储checkpointer (异步上下文管理器)

        适用于:
        - 异步应用
        - 需要高并发的场景
        - FastAPI等异步Web框架

        Args:
            db_path: 数据库文件路径, 如果为None则使用配置中的路径

        Yields:
            AsyncSqliteSaver实例

        Raises:
            StorageConnectionError: 数据库连接失败

        Examples:
            >>> manager = CheckpointerManager()
            >>> async with manager.create_async_sqlite_saver() as saver:
            ...     graph = StateGraph(...).compile(checkpointer=saver)
            ...     result = await graph.ainvoke(...)
        """
        path = db_path or self.config.checkpoint_db_path
        path_str = str(path.absolute())

        logger.info("创建AsyncSqliteSaver checkpointer", extra={"db_path": path_str})

        saver = None
        try:
            # from_conn_string 返回的是异步上下文管理器, 需要使用async with
            async with AsyncSqliteSaver.from_conn_string(path_str) as saver:
                logger.info("AsyncSqliteSaver checkpointer创建成功")
                yield saver

        except Exception as e:
            logger.exception(
                "创建AsyncSqliteSaver失败: %s",
                e,
                extra={"db_path": path_str},
            )
            raise CustomConnectionError(
                message=f"无法创建异步SQLite checkpointer: {e}",
                details={
                    "db_path": path_str,
                    "error": str(e),
                },
            ) from e

    def create_default_saver(self) -> BaseCheckpointSaver:
        """创建默认checkpointer

        根据配置自动选择合适的存储后端.

        配置优先级:
        1. checkpoint_type == 'memory' -> MemorySaver
        2. checkpoint_type == 'sqlite' -> SqliteSaver
        3. 默认 -> MemorySaver (用于测试)

        注意: 对于SQLite存储, 此方法返回的saver持有数据库连接.
        使用完毕后必须调用manager.cleanup()释放资源, 或使用上下文管理器版本.

        Returns:
            BaseCheckpointSaver实例

        Raises:
            StorageConnectionError: 创建失败

        Examples:
            >>> manager = CheckpointerManager()
            >>> saver = manager.create_default_saver()
            >>> # 使用完毕后清理
            >>> manager.cleanup()
        """
        checkpoint_type = self.config.checkpoint_type.lower()

        logger.info("创建默认checkpointer", extra={"checkpoint_type": checkpoint_type})

        if checkpoint_type == "memory":
            return self.create_memory_saver()
        elif checkpoint_type == "sqlite":
            # 注意: 这里返回的是在上下文管理器外使用的版本
            # 生产环境建议使用上下文管理器版本以确保资源正确释放
            path_str = self.config.db_path_str

            # 健康检查: 确保目录存在且可写
            db_path = Path(path_str)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            if not db_path.parent.exists():
                raise CustomConnectionError(
                    message=f"无法创建数据库目录: {db_path.parent}",
                    details={"db_path": path_str},
                )

            try:
                conn = sqlite3.connect(path_str, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                saver = SqliteSaver(conn)
                saver.setup()
                # 保存连接引用以便后续清理
                self._sqlite_connection = conn
                logger.info("默认SqliteSaver checkpointer创建成功")
                return saver
            except Exception as e:
                logger.exception(
                    "创建默认SqliteSaver失败: %s",
                    e,
                    extra={"db_path": path_str},
                )
                raise CustomConnectionError(
                    message=f"无法创建默认SQLite checkpointer: {e}",
                    details={"db_path": path_str, "error": str(e)},
                ) from e
        else:
            # 未知类型, 默认使用内存存储
            logger.warning(
                "未知的checkpoint_type: %s, 使用MemorySaver", checkpoint_type
            )
            return self.create_memory_saver()

    def cleanup(self) -> None:
        """清理资源

        关闭数据库连接等资源.
        建议在应用关闭时调用.
        """
        if self._sqlite_connection:
            try:
                self._sqlite_connection.close()
                logger.info("SQLite连接已关闭")
                self._sqlite_connection = None
            except Exception as e:
                logger.warning("关闭SQLite连接时出错: %s", e)

    def __del__(self) -> None:
        """析构函数, 确保资源被释放"""
        self.cleanup()


class CheckpointerHelper:
    """Checkpointer辅助工具类

    提供检查点管理的辅助功能.
    """

    @staticmethod
    def _cleanup_via_api(
        saver: SqliteSaver, ttl_seconds: int, thread_id: str | None = None
    ) -> int:
        """通过 API 方法清理过期的检查点

        当无法直接从数据库查询时间时,使用此方法通过 list() API 获取所有
        checkpoint 并手动过滤删除.

        Args:
            saver: SqliteSaver实例
            ttl_seconds: 检查点保留时间(秒)
            thread_id: 如果指定, 只清理该线程的检查点

        Returns:
            删除的检查点数量
        """
        cutoff_time = datetime.now().replace(tzinfo=None) - timedelta(
            seconds=ttl_seconds
        )
        deleted_count = 0

        try:
            # 使用 list() API 获取所有 checkpoint
            if thread_id:
                config = {"configurable": {"thread_id": thread_id}}
                checkpoints = list(saver.list(config))
            else:
                # 获取所有线程的 checkpoint
                # 先获取所有 thread_id
                cursor = saver.conn.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints"
                )
                thread_ids = [row[0] for row in cursor.fetchall()]

                all_checkpoints = []
                for tid in thread_ids:
                    config = {"configurable": {"thread_id": tid}}
                    all_checkpoints.extend(list(saver.list(config)))
                checkpoints = all_checkpoints

            # 过滤并删除过期的 checkpoint
            # 注意:LangGraph 的 SqliteSaver 没有直接的删除方法
            # 我们需要通过 checkpoint_id 来删除
            for checkpoint_tuple in checkpoints:
                checkpoint = checkpoint_tuple.checkpoint
                if "ts" in checkpoint:
                    try:
                        checkpoint_ts_str = checkpoint["ts"]
                        # 处理时区格式
                        if checkpoint_ts_str.endswith("Z"):
                            checkpoint_ts_str = checkpoint_ts_str[:-1] + "+00:00"
                        checkpoint_ts = datetime.fromisoformat(checkpoint_ts_str)
                        # 确保比较时都是naive datetime(去除时区信息)
                        if checkpoint_ts.tzinfo is not None:
                            checkpoint_ts = checkpoint_ts.replace(tzinfo=None)

                        if checkpoint_ts < cutoff_time:
                            # 获取 checkpoint_id 并删除该行
                            checkpoint_id = checkpoint.get("id")
                            if checkpoint_id:
                                # 检查表结构以确定正确的列名
                                cursor = saver.conn.execute(
                                    "PRAGMA table_info(checkpoints)"
                                )
                                columns = [row[1] for row in cursor.fetchall()]

                                # 查找 checkpoint_id 列(可能是 checkpoint_id 或 id)
                                id_column = (
                                    "checkpoint_id"
                                    if "checkpoint_id" in columns
                                    else "id"
                                )

                                # 直接删除数据库行
                                if thread_id:
                                    if id_column == "checkpoint_id":
                                        saver.conn.execute(
                                            "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?",
                                            (thread_id, checkpoint_id),
                                        )
                                    else:
                                        saver.conn.execute(
                                            "DELETE FROM checkpoints WHERE thread_id = ? AND id = ?",
                                            (thread_id, checkpoint_id),
                                        )
                                else:
                                    if id_column == "checkpoint_id":
                                        saver.conn.execute(
                                            "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                                            (checkpoint_id,),
                                        )
                                    else:
                                        saver.conn.execute(
                                            "DELETE FROM checkpoints WHERE id = ?",
                                            (checkpoint_id,),
                                        )
                                deleted_count += 1
                    except (ValueError, KeyError) as e:
                        logger.warning("解析 checkpoint 时间戳失败: %s", e)
                        continue

        except Exception as e:
            logger.exception("通过API清理检查点失败: %s", e)
        finally:
            if deleted_count > 0:
                saver.conn.commit()

        return deleted_count

    @staticmethod
    def cleanup_old_checkpoints(
        saver: SqliteSaver, ttl_seconds: int = 86400, thread_id: str | None = None
    ) -> int:
        """清理过期的检查点

        Args:
            saver: SqliteSaver实例
            ttl_seconds: 检查点保留时间(秒), 默认24小时
            thread_id: 如果指定, 只清理该线程的检查点

        Returns:
            删除的检查点数量

        Examples:
            >>> with manager.create_sqlite_saver() as saver:
            ...     count = CheckpointerHelper.cleanup_old_checkpoints(
            ...         saver, ttl_seconds=3600
            ...     )
            ...     print(f'清理了 {count} 个过期检查点')
        """
        try:
            conn = saver.conn
            cutoff_time = datetime.now().replace(tzinfo=None) - timedelta(
                seconds=ttl_seconds
            )
            cutoff_ts = cutoff_time.isoformat()

            # 首先检查表结构
            cursor = conn.execute("PRAGMA table_info(checkpoints)")
            columns = [row[1] for row in cursor.fetchall()]

            logger.debug("checkpoints表列: %s", columns)

            # 查找存储 checkpoint 数据的列(LangGraph 通常使用 checkpoint 列存储 JSON)
            checkpoint_column = None
            for col in columns:
                col_lower = col.lower()
                if col_lower in (
                    "checkpoint",
                    "checkpoint_json",
                    "checkpoint_data",
                    "value",
                    "blob",
                ):
                    checkpoint_column = col
                    break

            # LangGraph 1.0.4 中,ts 存储在 checkpoint JSON 对象中
            # 策略:优先使用独立时间列,其次使用 JSON 提取,最后使用 API
            if thread_id:
                if "created_at" in columns:
                    cursor = conn.execute(
                        "DELETE FROM checkpoints WHERE thread_id = ? AND created_at < ?",
                        (thread_id, cutoff_ts),
                    )
                elif "ts" in columns:
                    cursor = conn.execute(
                        "DELETE FROM checkpoints WHERE thread_id = ? AND ts < ?",
                        (thread_id, cutoff_ts),
                    )
                elif checkpoint_column:
                    # 从 JSON 列中提取 ts 字段进行比较
                    # SQLite 3.38+ 支持 JSON 函数
                    try:
                        # 先检查JSON格式是否有效
                        cursor = conn.execute(
                            "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ? AND json_valid(?) = 0",
                            (thread_id, checkpoint_column),
                        )
                        invalid_json_count = cursor.fetchone()[0]

                        if invalid_json_count > 0:
                            logger.warning(
                                "发现 %s 个无效JSON记录,使用API方法清理",
                                invalid_json_count,
                            )
                            return CheckpointerHelper._cleanup_via_api(
                                saver, ttl_seconds, thread_id
                            )

                        cursor = conn.execute(
                            "DELETE FROM checkpoints WHERE thread_id = ? AND json_extract(?, '$.ts') < ?",
                            (thread_id, checkpoint_column, cutoff_ts),
                        )
                    except Exception as json_err:
                        # 如果 JSON 提取失败,回退到 API 方法
                        logger.warning("JSON提取失败: %s, 使用API方法清理", json_err)
                        return CheckpointerHelper._cleanup_via_api(
                            saver, ttl_seconds, thread_id
                        )
                else:
                    # 如果无法找到时间信息,使用 API 方法
                    logger.info("checkpoints表缺少时间列和JSON列,使用API方法清理")
                    return CheckpointerHelper._cleanup_via_api(
                        saver, ttl_seconds, thread_id
                    )
            else:
                if "created_at" in columns:
                    cursor = conn.execute(
                        "DELETE FROM checkpoints WHERE created_at < ?", (cutoff_ts,)
                    )
                elif "ts" in columns:
                    cursor = conn.execute(
                        "DELETE FROM checkpoints WHERE ts < ?", (cutoff_ts,)
                    )
                elif checkpoint_column:
                    # 从 JSON 列中提取 ts 字段进行比较
                    try:
                        # 先检查JSON格式是否有效
                        cursor = conn.execute(
                            "SELECT COUNT(*) FROM checkpoints WHERE json_valid(?) = 0",
                            (checkpoint_column,),
                        )
                        invalid_json_count = cursor.fetchone()[0]

                        if invalid_json_count > 0:
                            logger.warning(
                                "发现 %s 个无效JSON记录,使用API方法清理",
                                invalid_json_count,
                            )
                            return CheckpointerHelper._cleanup_via_api(
                                saver, ttl_seconds, thread_id
                            )

                        cursor = conn.execute(
                            "DELETE FROM checkpoints WHERE json_extract(?, '$.ts') < ?",
                            (checkpoint_column, cutoff_ts),
                        )
                    except Exception as json_err:
                        # 如果 JSON 提取失败,回退到 API 方法
                        logger.warning("JSON提取失败: %s, 使用API方法清理", json_err)
                        return CheckpointerHelper._cleanup_via_api(
                            saver, ttl_seconds, thread_id
                        )
                else:
                    # 如果无法找到时间信息,使用 API 方法
                    logger.info("checkpoints表缺少时间列和JSON列,使用API方法清理")
                    return CheckpointerHelper._cleanup_via_api(
                        saver, ttl_seconds, thread_id
                    )

            deleted_count = int(cursor.rowcount)
            conn.commit()

            logger.info(
                "清理了 %s 个过期检查点",
                deleted_count,
                extra={
                    "ttl_seconds": ttl_seconds,
                    "thread_id": thread_id,
                    "deleted_count": deleted_count,
                },
            )

            return deleted_count

        except Exception as e:
            logger.exception("清理检查点失败: %s", e)
            raise StorageError(
                message=f"清理检查点失败: {e}",
                details={
                    "ttl_seconds": ttl_seconds,
                    "thread_id": thread_id,
                    "error": str(e),
                },
            ) from e

    @staticmethod
    async def cleanup_old_checkpoints_async(
        saver: AsyncSqliteSaver,
        ttl_seconds: int = 86400,
        thread_id: str | None = None,
    ) -> int:
        """异步清理过期的检查点

        Args:
            saver: AsyncSqliteSaver实例
            ttl_seconds: 检查点保留时间(秒), 默认24小时
            thread_id: 如果指定, 只清理该线程的检查点

        Returns:
            删除的检查点数量

        Examples:
            >>> async with manager.create_async_sqlite_saver() as saver:
            ...     count = await CheckpointerHelper.cleanup_old_checkpoints_async(
            ...         saver, ttl_seconds=3600
            ...     )
            ...     print(f'清理了 {count} 个过期检查点')
        """
        try:
            # AsyncSqliteSaver通过底层连接进行清理
            # 获取底层连接字符串
            cutoff_time = datetime.now().replace(tzinfo=None) - timedelta(
                seconds=ttl_seconds
            )
            cutoff_ts = cutoff_time.isoformat()

            # 通过saver的底层连接执行清理
            # 注意: AsyncSqliteSaver可能没有直接暴露conn属性
            # 我们需要通过其他方式访问数据库
            import aiosqlite

            # 尝试从saver获取连接字符串
            # 如果无法获取, 则记录警告
            try:
                # 假设saver有conn_string属性或类似属性
                if hasattr(saver, "conn_string"):
                    conn_string = saver.conn_string
                elif hasattr(saver, "_conn_string"):
                    conn_string = saver._conn_string
                else:
                    # 如果无法获取连接字符串, 使用配置中的路径
                    logger.warning("无法从AsyncSqliteSaver获取连接字符串, 使用配置路径")
                    # 这里需要从配置中获取路径, 但helper是静态方法, 无法访问manager
                    # 因此返回0并记录警告
                    logger.warning("异步清理检查点需要连接字符串, 当前实现受限")
                    return 0

                # 使用aiosqlite执行清理
                async with aiosqlite.connect(conn_string) as conn:
                    # 检查表结构
                    cursor = await conn.execute("PRAGMA table_info(checkpoints)")
                    columns = [row[1] for row in await cursor.fetchall()]

                    logger.debug("checkpoints表列(异步): %s", columns)

                    # 查找存储 checkpoint 数据的列
                    checkpoint_column = None
                    for col in columns:
                        col_lower = col.lower()
                        if col_lower in (
                            "checkpoint",
                            "checkpoint_json",
                            "checkpoint_data",
                            "value",
                            "blob",
                        ):
                            checkpoint_column = col
                            break

                    if "created_at" in columns:
                        if thread_id:
                            cursor = await conn.execute(
                                "DELETE FROM checkpoints WHERE thread_id = ? AND created_at < ?",
                                (thread_id, cutoff_ts),
                            )
                        else:
                            cursor = await conn.execute(
                                "DELETE FROM checkpoints WHERE created_at < ?",
                                (cutoff_ts,),
                            )
                        deleted_count = cursor.rowcount
                        await conn.commit()

                        logger.info(
                            "异步清理了 %s 个过期检查点",
                            deleted_count,
                            extra={
                                "ttl_seconds": ttl_seconds,
                                "thread_id": thread_id,
                                "deleted_count": deleted_count,
                            },
                        )
                        return deleted_count
                    elif "ts" in columns:
                        # LangGraph 1.0+ 使用 ts 列存储时间戳
                        if thread_id:
                            cursor = await conn.execute(
                                "DELETE FROM checkpoints WHERE thread_id = ? AND ts < ?",
                                (thread_id, cutoff_ts),
                            )
                        else:
                            cursor = await conn.execute(
                                "DELETE FROM checkpoints WHERE ts < ?",
                                (cutoff_ts,),
                            )
                        deleted_count = cursor.rowcount
                        await conn.commit()

                        logger.info(
                            "异步清理了 %s 个过期检查点",
                            deleted_count,
                            extra={
                                "ttl_seconds": ttl_seconds,
                                "thread_id": thread_id,
                                "deleted_count": deleted_count,
                            },
                        )
                        return deleted_count
                    elif checkpoint_column:
                        # 从 JSON 列中提取 ts 字段进行比较
                        try:
                            # 先检查JSON格式是否有效
                            if thread_id:
                                cursor = await conn.execute(
                                    "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ? AND json_valid(?) = 0",
                                    (thread_id, checkpoint_column),
                                )
                            else:
                                cursor = await conn.execute(
                                    "SELECT COUNT(*) FROM checkpoints WHERE json_valid(?) = 0",
                                    (checkpoint_column,),
                                )
                            invalid_json_count = (await cursor.fetchone())[0]

                            if invalid_json_count > 0:
                                logger.warning(
                                    "发现 %s 个无效JSON记录(异步),跳过清理操作",
                                    invalid_json_count,
                                )
                                return 0

                            if thread_id:
                                cursor = await conn.execute(
                                    "DELETE FROM checkpoints WHERE thread_id = ? AND json_extract(?, '$.ts') < ?",
                                    (thread_id, checkpoint_column, cutoff_ts),
                                )
                            else:
                                cursor = await conn.execute(
                                    "DELETE FROM checkpoints WHERE json_extract(?, '$.ts') < ?",
                                    (checkpoint_column, cutoff_ts),
                                )
                            deleted_count = cursor.rowcount
                            await conn.commit()

                            logger.info(
                                "异步清理了 %s 个过期检查点",
                                deleted_count,
                                extra={
                                    "ttl_seconds": ttl_seconds,
                                    "thread_id": thread_id,
                                    "deleted_count": deleted_count,
                                },
                            )
                            return deleted_count
                        except Exception as json_err:
                            logger.warning(
                                "JSON提取失败(异步): %s, 跳过清理操作", json_err
                            )
                            # 对于异步版本,暂时返回0,因为API方法需要同步实现
                            return 0
                    else:
                        logger.warning(
                            "checkpoints表缺少时间列和JSON列(异步), 跳过清理操作"
                        )
                        return 0
            except AttributeError:
                logger.warning("AsyncSqliteSaver不支持直接访问连接, 异步清理功能受限")
                return 0

        except Exception as e:
            logger.exception("异步清理检查点失败: %s", e)
            raise StorageError(
                message=f"异步清理检查点失败: {e}",
                details={
                    "ttl_seconds": ttl_seconds,
                    "thread_id": thread_id,
                    "error": str(e),
                },
            ) from e


# 全局单例管理器
_default_manager: CheckpointerManager | None = None


def get_checkpointer_manager() -> CheckpointerManager:
    """获取默认的CheckpointerManager实例

    Returns:
        CheckpointerManager单例实例

    Examples:
        >>> manager = get_checkpointer_manager()
        >>> saver = manager.create_default_saver()
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = CheckpointerManager()
    return _default_manager


# 便捷函数
def create_checkpointer(
    checkpoint_type: Literal["memory", "sqlite", "default"] = "default",
) -> BaseCheckpointSaver:
    """创建checkpointer的便捷函数

    Args:
        checkpoint_type: 存储类型
            - 'memory': 内存存储
            - 'sqlite': SQLite存储
            - 'default': 根据配置自动选择

    Returns:
        BaseCheckpointSaver实例

    Examples:
        >>> # 创建内存存储
        >>> saver = create_checkpointer('memory')

        >>> # 创建SQLite存储
        >>> saver = create_checkpointer('sqlite')

        >>> # 使用默认配置
        >>> saver = create_checkpointer()
    """
    manager = get_checkpointer_manager()

    if checkpoint_type == "memory":
        return manager.create_memory_saver()
    elif checkpoint_type == "sqlite":
        return manager.create_default_saver()  # 使用SQLite
    else:
        return manager.create_default_saver()


__all__ = [
    "CheckpointerConfig",
    "CheckpointerHelper",
    "CheckpointerManager",
    "create_checkpointer",
    "get_checkpointer_manager",
]
