"""
大纲优化接受/拒绝功能测试

该模块测试大纲优化服务的接受/拒绝优化建议功能。
用于T215任务验证。
"""

# 生成命令: /speckit.implement T215
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import json
import uuid
from datetime import UTC, datetime

import pytest

from src.application.services.outline_optimization_service import OutlineOptimizationService
from src.domain.agent.optimized_outline import (
    OptimizationChangeType,
    OptimizationSummary,
    OptimizedOutline,
    OptimizedOutlineItem,
)
from src.domain.agent.outline import Outline, OutlineItem, OutlineItemType, OutlineStatus
from src.infrastructure.storage.sqlite.connection import create_connection_manager
from src.shared.exceptions.base_exceptions import ResourceNotFoundError, ValidationError


def execute_sql_file(conn_manager, file_path):
    """执行SQL文件
    
    只执行 -- @up 部分的SQL语句，按分号分割语句。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        sql = f.read()
    
    # 只执行 -- @up 部分（在 -- @down 之前）
    down_marker = "-- @down"
    if down_marker in sql:
        sql = sql.split(down_marker)[0].strip()
    
    # 分割SQL语句（按分号分割）
    statements = []
    current_statement = []
    
    for line in sql.split('\n'):
        stripped = line.strip()
        
        # 跳过空行和注释行
        if not stripped or stripped.startswith('--'):
            continue
        
        current_statement.append(line)
        
        # 如果行以分号结尾，表示语句结束
        if stripped.endswith(';'):
            statement = '\n'.join(current_statement).strip()
            if statement:
                statements.append(statement)
            current_statement = []
    
    # 添加最后一个语句（如果没有以分号结尾）
    if current_statement:
        statement = '\n'.join(current_statement).strip()
        if statement:
            statements.append(statement)
    
    # 执行所有SQL语句
    with conn_manager.get_connection() as conn:
        cursor = conn.cursor()
        for statement in statements:
            if statement.strip():
                cursor.execute(statement)
        conn.commit()


@pytest.fixture
def db_connection():
    """创建数据库连接"""
    # 创建内存数据库连接管理器
    conn_manager = create_connection_manager(database_path=":memory:")
    
    # 执行迁移脚本
    execute_sql_file(conn_manager, "scripts/migration/migrations/003_create_industries_tables.sql")
    execute_sql_file(conn_manager, "scripts/migration/migrations/005_create_outline_optimization_table.sql")
    
    yield conn_manager
    
    conn_manager.close()


@pytest.fixture
def service(db_connection):
    """创建大纲优化服务"""
    return OutlineOptimizationService(connection_manager=db_connection)


@pytest.fixture
def sample_industry(db_connection):
    """创建示例行业
    
    使用迁移脚本中已存在的ENERGY_STORAGE行业，避免唯一约束冲突。
    """
    # 迁移脚本003_create_industries_tables.sql已经插入了ENERGY_STORAGE行业
    # 使用其ID: '00000000-0000-0000-0000-000000000001'
    industry_id = '00000000-0000-0000-0000-000000000001'
    
    # 验证该行业是否存在，如果不存在则创建
    with db_connection.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM industries WHERE code = ?", ("ENERGY_STORAGE",))
        result = cursor.fetchone()
        if not result:
            # 如果不存在则创建
            now = datetime.now(UTC).isoformat()
            cursor.execute(
                "INSERT INTO industries (id, name, code, category, description, is_active, sort_order, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    industry_id,
                    "储能行业",
                    "ENERGY_STORAGE",
                    "ENERGY",
                    "储能行业",
                    True,
                    1,
                    now,
                    now,
                    "{}",
                ),
            )
            conn.commit()
        else:
            industry_id = result[0]
    
    return industry_id


@pytest.fixture
def sample_outline(sample_industry):
    """创建示例大纲"""
    outline = Outline(
        title="储能产业发展报告",
        description="储能产业发展报告大纲",
        industry_id=uuid.UUID(sample_industry),
        database_ids=[],
        status=OutlineStatus.DRAFT,
    )
    
    # 添加大纲项
    item1 = OutlineItem(
        parent_id=None,
        item_type=OutlineItemType.SECTION,
        level=1,
        title="市场概况",
        description="储能市场概况",
        order=1,
    )
    outline.add_item(item1)
    
    item2 = OutlineItem(
        parent_id=item1.id,
        item_type=OutlineItemType.SUBSECTION,
        level=2,
        title="市场规模",
        description="储能市场规模分析",
        order=1,
    )
    outline.add_item(item2)
    
    item3 = OutlineItem(
        parent_id=item1.id,
        item_type=OutlineItemType.SUBSECTION,
        level=2,
        title="发展趋势",
        description="储能市场发展趋势",
        order=2,
    )
    outline.add_item(item3)
    
    item4 = OutlineItem(
        parent_id=None,
        item_type=OutlineItemType.SECTION,
        level=1,
        title="技术分析",
        description="储能技术分析",
        order=2,
    )
    outline.add_item(item4)
    
    return outline


@pytest.fixture
def sample_optimized_outline(sample_outline):
    """创建示例优化后的大纲"""
    optimized_outline = OptimizedOutline(
        original_outline_id=sample_outline.id,
    )
    
    # 添加优化项 - 修改
    item1 = OutlineItem(
        parent_id=None,
        item_type=OutlineItemType.SECTION,
        level=1,
        title="市场概况与发展趋势",
        description="储能市场概况与发展趋势",
        order=1,
    )
    optimized_item1 = OptimizedOutlineItem(
        original_outline_id=sample_outline.id,
        original_item_id=sample_outline.items[0].id,
        original_item=sample_outline.items[0],
        optimized_item=item1,
        change_type=OptimizationChangeType.MODIFY,
        change_description="合并市场概况和发展趋势",
        optimization_reason="提高大纲结构完整性",
        optimization_suggestions=["将市场概况和发展趋势合并为一个章节"],
    )
    optimized_outline.add_optimized_item(optimized_item1)
    
    # 添加优化项 - 新增
    item2 = OutlineItem(
        parent_id=None,
        item_type=OutlineItemType.SECTION,
        level=1,
        title="政策环境",
        description="储能政策环境分析",
        order=3,
    )
    optimized_item2 = OptimizedOutlineItem(
        original_outline_id=sample_outline.id,
        original_item_id=None,
        optimized_item=item2,
        change_type=OptimizationChangeType.ADD,
        change_description="新增政策环境章节",
        optimization_reason="补充政策分析内容",
        optimization_suggestions=["添加政策环境分析章节"],
    )
    optimized_outline.add_optimized_item(optimized_item2)
    
    # 添加优化项 - 删除
    item3 = OutlineItem(
        parent_id=None,
        item_type=OutlineItemType.SECTION,
        level=1,
        title="技术分析",
        description="储能技术分析",
        order=2,
    )
    optimized_item3 = OptimizedOutlineItem(
        original_outline_id=sample_outline.id,
        original_item_id=sample_outline.items[3].id,
        original_item=sample_outline.items[3],
        optimized_item=item3,
        change_type=OptimizationChangeType.DELETE,
        change_description="删除技术分析章节",
        optimization_reason="技术分析内容可以合并到其他章节",
        optimization_suggestions=["删除技术分析章节"],
    )
    optimized_outline.add_optimized_item(optimized_item3)
    
    # 添加优化摘要
    summary = OptimizationSummary(
        optimized_outline_id=optimized_outline.id,
        total_changes=3,
        added_items=1,
        modified_items=1,
        deleted_items=1,
        moved_items=0,
        reordered_items=0,
        merged_items=0,
        split_items=0,
        quality_score=0.85,
        completeness_score=0.9,
        coherence_score=0.8,
        relevance_score=0.85,
        optimization_summary="优化大纲结构，提高完整性和连贯性",
        key_improvements=["合并相关章节", "新增政策环境分析"],
        potential_issues=["技术分析内容需要重新组织"],
    )
    optimized_outline.set_summary(summary)
    
    return optimized_outline


class TestOutlineOptimizationService:
    """大纲优化服务测试"""

    def test_save_outline(self, service, sample_outline):
        """测试保存大纲"""
        result = service.save_outline(sample_outline)
        
        assert result["id"] == str(sample_outline.id)
        assert result["title"] == sample_outline.title
        assert result["status"] == OutlineStatus.DRAFT.value
        assert len(result["items"]) == 4

    def test_get_outline(self, service, sample_outline):
        """测试获取大纲"""
        service.save_outline(sample_outline)
        
        result = service.get_outline(str(sample_outline.id))
        
        assert result["outline"]["id"] == str(sample_outline.id)
        assert result["outline"]["title"] == sample_outline.title
        assert len(result["items"]) == 4
        assert len(result["versions"]) == 0

    def test_get_outline_not_found(self, service):
        """测试获取不存在的大纲"""
        with pytest.raises(ResourceNotFoundError):
            service.get_outline(str(uuid.uuid4()))

    def test_save_optimized_outline(self, service, sample_outline, sample_optimized_outline):
        """测试保存优化后的大纲"""
        # 先保存原始大纲
        service.save_outline(sample_outline)
        
        result = service.save_optimized_outline(sample_optimized_outline)
        
        assert result["id"] == str(sample_optimized_outline.id)
        assert result["original_outline_id"] == str(sample_outline.id)
        assert result["optimization_status"] == "PENDING"
        assert len(result["optimized_items"]) == 3

    def test_get_optimized_outline(self, service, sample_outline, sample_optimized_outline):
        """测试获取优化后的大纲"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        result = service.get_optimized_outline(str(sample_optimized_outline.id))
        
        assert result["optimized_outline"]["id"] == str(sample_optimized_outline.id)
        assert result["optimized_outline"]["original_outline_id"] == str(sample_outline.id)
        assert len(result["items"]) == 3
        assert result["summary"] is not None

    def test_get_optimized_outline_not_found(self, service):
        """测试获取不存在的优化后大纲"""
        with pytest.raises(ResourceNotFoundError):
            service.get_optimized_outline(str(uuid.uuid4()))

    def test_accept_optimization_item(self, service, sample_outline, sample_optimized_outline):
        """测试接受单个优化项"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        # 接受第一个优化项
        item_id = sample_optimized_outline.optimized_items[0].id
        result = service.accept_optimization_item(
            str(sample_optimized_outline.id), str(item_id), feedback="接受此优化"
        )
        
        assert result["is_accepted"] is True
        assert result["user_feedback"] == "接受此优化"

    def test_accept_optimization_item_not_found(self, service, sample_outline):
        """测试接受不存在的优化项"""
        service.save_outline(sample_outline)
        
        with pytest.raises(ResourceNotFoundError):
            service.accept_optimization_item(
                str(uuid.uuid4()), str(uuid.uuid4()), feedback="接受此优化"
            )

    def test_reject_optimization_item(self, service, sample_outline, sample_optimized_outline):
        """测试拒绝单个优化项"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        # 拒绝第一个优化项
        item_id = sample_optimized_outline.optimized_items[0].id
        result = service.reject_optimization_item(
            str(sample_optimized_outline.id), str(item_id), feedback="拒绝此优化"
        )
        
        assert result["is_accepted"] is False
        assert result["user_feedback"] == "拒绝此优化"

    def test_accept_all_optimizations(self, service, sample_outline, sample_optimized_outline):
        """测试接受所有优化建议"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        result = service.accept_all_optimizations(
            str(sample_optimized_outline.id), feedback="全部接受"
        )
        
        assert result["is_accepted"] is True
        assert result["user_feedback"] == "全部接受"
        assert result["optimization_status"] == "ACCEPTED"

    def test_reject_all_optimizations(self, service, sample_outline, sample_optimized_outline):
        """测试拒绝所有优化建议"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        result = service.reject_all_optimizations(
            str(sample_optimized_outline.id), feedback="全部拒绝"
        )
        
        assert result["is_accepted"] is False
        assert result["user_feedback"] == "全部拒绝"
        assert result["optimization_status"] == "REJECTED"

    def test_generate_final_outline_accept_all(self, service, sample_outline, sample_optimized_outline):
        """测试生成最终大纲 - 接受所有优化"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        # 接受所有优化
        service.accept_all_optimizations(str(sample_optimized_outline.id))
        
        # 生成最终大纲
        result = service.generate_final_outline(
            str(sample_optimized_outline.id), str(sample_outline.id)
        )
        
        assert result["status"] == OutlineStatus.ACCEPTED.value
        # 应该包含修改后的章节和新增的章节，不包含删除的章节
        assert len(result["items"]) == 2

    def test_generate_final_outline_reject_all(self, service, sample_outline, sample_optimized_outline):
        """测试生成最终大纲 - 拒绝所有优化"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        # 拒绝所有优化
        service.reject_all_optimizations(str(sample_optimized_outline.id))
        
        # 生成最终大纲
        result = service.generate_final_outline(
            str(sample_optimized_outline.id), str(sample_outline.id)
        )
        
        assert result["status"] == OutlineStatus.ACCEPTED.value
        # 应该保留原始大纲的所有项
        assert len(result["items"]) == 4

    def test_generate_final_outline_partial_accept(self, service, sample_outline, sample_optimized_outline):
        """测试生成最终大纲 - 部分接受"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        # 接受第一个优化项（修改），拒绝其他
        item_id = sample_optimized_outline.optimized_items[0].id
        service.accept_optimization_item(str(sample_optimized_outline.id), str(item_id))
        
        # 生成最终大纲
        result = service.generate_final_outline(
            str(sample_optimized_outline.id), str(sample_outline.id)
        )
        
        assert result["status"] == OutlineStatus.ACCEPTED.value
        # 应该包含修改后的章节和原始的其他章节
        assert len(result["items"]) == 4

    def test_get_optimization_history(self, service, sample_outline, sample_optimized_outline):
        """测试获取优化历史"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        result = service.get_optimization_history(str(sample_outline.id))
        
        assert len(result) == 1
        assert result[0]["optimized_outline"]["id"] == str(sample_optimized_outline.id)
        assert result[0]["statistics"]["total_items"] == 3

    def test_get_optimization_status(self, service, sample_outline, sample_optimized_outline):
        """测试获取优化状态"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        result = service.get_optimization_status(str(sample_optimized_outline.id))
        
        assert result["total_items"] == 3
        assert result["accepted_items"] == 0
        assert result["rejected_items"] == 0
        assert result["pending_items"] == 3
        assert result["completion_rate"] == 0.0

    def test_get_optimization_status_after_accept(self, service, sample_outline, sample_optimized_outline):
        """测试获取优化状态 - 接受后"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        # 接受一个优化项
        item_id = sample_optimized_outline.optimized_items[0].id
        service.accept_optimization_item(str(sample_optimized_outline.id), str(item_id))
        
        result = service.get_optimization_status(str(sample_optimized_outline.id))
        
        assert result["total_items"] == 3
        assert result["accepted_items"] == 1
        assert result["pending_items"] == 2
        assert result["completion_rate"] == 33.33

    def test_validate_uuid_invalid(self, service):
        """测试无效UUID验证"""
        with pytest.raises(ValidationError):
            service.get_outline("invalid-uuid")

    def test_save_outline_with_version(self, service, sample_outline):
        """测试保存带版本的大纲"""
        # 创建版本
        version = sample_outline.create_version(
            OutlineStatus.DRAFT, change_reason="初始版本"
        )
        
        service.save_outline(sample_outline)
        
        result = service.get_outline(str(sample_outline.id))
        
        assert len(result["versions"]) == 1
        assert result["versions"][0]["version_number"] == 2
        assert result["versions"][0]["change_reason"] == "初始版本"

    def test_save_optimized_outline_with_summary(self, service, sample_outline, sample_optimized_outline):
        """测试保存带摘要的优化后大纲"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        result = service.get_optimized_outline(str(sample_optimized_outline.id))
        
        assert result["summary"] is not None
        assert result["summary"]["total_changes"] == 3
        assert result["summary"]["quality_score"] == 0.85

    def test_get_optimization_history_empty(self, service, sample_outline):
        """测试获取空优化历史"""
        service.save_outline(sample_outline)
        
        result = service.get_optimization_history(str(sample_outline.id))
        
        assert len(result) == 0

    def test_change_type_statistics(self, service, sample_outline, sample_optimized_outline):
        """测试变更类型统计"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        result = service.get_optimization_status(str(sample_optimized_outline.id))
        
        assert "change_type_stats" in result
        assert result["change_type_stats"]["ADD"]["total"] == 1
        assert result["change_type_stats"]["MODIFY"]["total"] == 1
        assert result["change_type_stats"]["DELETE"]["total"] == 1

    def test_accept_item_with_feedback(self, service, sample_outline, sample_optimized_outline):
        """测试接受优化项并添加反馈"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        item_id = sample_optimized_outline.optimized_items[0].id
        feedback = "这个优化很好，我接受"
        result = service.accept_optimization_item(
            str(sample_optimized_outline.id), str(item_id), feedback=feedback
        )
        
        assert result["user_feedback"] == feedback

    def test_reject_item_with_feedback(self, service, sample_outline, sample_optimized_outline):
        """测试拒绝优化项并添加反馈"""
        service.save_outline(sample_outline)
        service.save_optimized_outline(sample_optimized_outline)
        
        item_id = sample_optimized_outline.optimized_items[0].id
        feedback = "这个优化不符合我的需求"
        result = service.reject_optimization_item(
            str(sample_optimized_outline.id), str(item_id), feedback=feedback
        )
        
        assert result["user_feedback"] == feedback
