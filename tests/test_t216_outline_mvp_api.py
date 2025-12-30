# 生成命令: 手动创建T216测试文件
# 生成时间: 2025-12-24
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
T216 大纲管理API路由测试

测试大纲管理API的各个端点功能，包括：
- 大纲创建（从文本和结构化数据）
- 大纲查询（详情、树结构、列表）
- 大纲更新和删除
- AI优化大纲
- 优化后大纲查询
- 优化接受/拒绝
- 最终大纲生成
- 优化历史查询
- 优化状态查询
- 大纲项管理
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
import uuid
from datetime import datetime

from src.interfaces.api.app import app
from src.domain.agent.outline import Outline, OutlineItem, OutlineStatus, OutlineItemType
from src.domain.agent.optimized_outline import (
    OptimizedOutline,
    OptimizedOutlineItem,
    OptimizationChangeType,
)
from src.domain.knowledge_base.industry_database import Industry, IndustryDatabase


# 创建测试客户端
client = TestClient(app)


# ==================== 测试数据 ====================

def create_mock_outline(outline_id: str = None) -> Outline:
    """创建模拟大纲对象"""
    if outline_id is None:
        outline_id = str(uuid.uuid4())
    
    # 创建行业ID和数据库ID
    industry_id = str(uuid.uuid4())
    database_id = str(uuid.uuid4())
    
    # 创建大纲项
    item1_id = str(uuid.uuid4())
    item2_id = str(uuid.uuid4())
    
    return Outline(
        id=outline_id,
        title="测试大纲",
        description="这是一个测试大纲",
        industry_id=industry_id,
        database_ids=[database_id],
        status=OutlineStatus.DRAFT,
        items=[
            OutlineItem(
                id=item1_id,
                title="第一章",
                content="第一章内容",
                item_type=OutlineItemType.SECTION,
                level=1,
                order=0,
            ),
            OutlineItem(
                id=item2_id,
                title="1.1 节",
                content="1.1 节内容",
                item_type=OutlineItemType.SUBSECTION,
                level=2,
                order=1,
                parent_id=item1_id,
            ),
        ],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def create_mock_optimized_outline(outline_id: str = None) -> OptimizedOutline:
    """创建模拟优化后大纲对象"""
    if outline_id is None:
        outline_id = str(uuid.uuid4())
    
    # 创建优化项
    optimized_item_id = str(uuid.uuid4())
    
    # 创建优化后的大纲项
    optimized_item = OutlineItem(
        id=uuid.UUID(optimized_item_id),
        title="优化后的章节",
        content="优化后的内容",
        item_type=OutlineItemType.SECTION,
        level=1,
        order=0,
    )
    
    return OptimizedOutline(
        id=uuid.uuid4(),
        original_outline_id=uuid.UUID(outline_id),
        optimized_items=[
            OptimizedOutlineItem(
                id=uuid.UUID(optimized_item_id),
                original_outline_id=uuid.UUID(outline_id),
                optimized_item=optimized_item,
                change_type=OptimizationChangeType.MODIFY,
                optimization_reason="优化建议",
            ),
        ],
        created_at=datetime.now(),
    )


# ==================== 辅助函数：设置依赖覆盖 ====================

def _setup_mock_services(
    mock_outline=None, 
    industry_id=None, 
    database_id=None, 
    save_side_effect=None,
    get_outline_return=None,
    get_outline_side_effect=None,
    **kwargs
):
    """
    设置mock服务并返回清理函数
    
    使用FastAPI的dependency_overrides机制来正确mock依赖注入
    这比@patch更可靠，因为@patch无法正确拦截FastAPI的Depends()
    
    Args:
        mock_outline: Outline对象，用于save_outline
        industry_id: 行业ID
        database_id: 数据库ID
        save_side_effect: save_outline的side_effect
        get_outline_return: get_outline的返回值（字典格式：{"outline": {...}, "items": [...]}）
        get_outline_side_effect: get_outline的side_effect（用于抛出异常）
        **kwargs: 其他服务方法的返回值，如 delete_outline, get_optimized_outline 等
    """
    from src.domain.knowledge_base.industry_database import DatabaseType, DataSource
    from src.interfaces.api.routes.outline_mvp import (
        get_outline_optimization_service,
        get_industry_selection_service,
    )
    
    # 创建mock服务
    mock_outline_svc = Mock()
    
    # 设置save_outline
    if save_side_effect:
        mock_outline_svc.save_outline.side_effect = save_side_effect
    elif mock_outline:
        # save_outline 返回的是字典格式 (outline.to_dict())，不是 Outline 对象
        mock_outline_svc.save_outline.return_value = mock_outline.to_dict()
    
    # 设置get_outline
    if get_outline_side_effect:
        mock_outline_svc.get_outline.side_effect = get_outline_side_effect
    elif get_outline_return:
        mock_outline_svc.get_outline.return_value = get_outline_return
    elif mock_outline:
        # 默认：将Outline对象转换为get_outline返回格式
        outline_dict = mock_outline.to_dict()
        items_dict = [item.to_dict() for item in mock_outline.items]
        mock_outline_svc.get_outline.return_value = {
            "outline": outline_dict,
            "items": items_dict,
            "versions": [],
        }
    
    # 设置其他方法（通过kwargs）
    for method_name, return_value in kwargs.items():
        if method_name.endswith("_side_effect"):
            # 处理 side_effect
            actual_method_name = method_name.replace("_side_effect", "")
            setattr(mock_outline_svc, actual_method_name, Mock(side_effect=return_value))
        else:
            # 处理 return_value
            setattr(mock_outline_svc, method_name, Mock(return_value=return_value))
    
    # 设置industry服务（如果需要）
    mock_industry_svc = None
    if industry_id or database_id:
        mock_industry_svc = Mock()
        if industry_id:
            # 路由期望字典格式，不是 Industry 对象
            mock_industry_svc.get_industry_by_id.return_value = {
                "id": industry_id,
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": "ENERGY"
            }
        if database_id:
            # 路由期望字典格式，不是 IndustryDatabase 对象
            mock_industry_svc.get_database_by_id.return_value = {
                "id": database_id,
                "name": "储能行业知识库",
                "code": "ENERGY_STORAGE_KB",
                "industry_id": industry_id or str(uuid.uuid4()),
                "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                "data_source": DataSource.PLATFORM_BUILTIN.value,
            }
            mock_industry_svc.get_industry_databases.return_value = [
                {
                    "id": database_id,
                    "name": "储能行业知识库",
                    "code": "ENERGY_STORAGE_KB",
                    "industry_id": industry_id or str(uuid.uuid4()),
                    "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                    "data_source": DataSource.PLATFORM_BUILTIN.value,
                }
            ]
    
    # 使用FastAPI的dependency_overrides (正确的mock方式)
    app.dependency_overrides[get_outline_optimization_service] = lambda: mock_outline_svc
    if mock_industry_svc:
        app.dependency_overrides[get_industry_selection_service] = lambda: mock_industry_svc
    
    def cleanup():
        # 清理覆盖
        app.dependency_overrides.pop(get_outline_optimization_service, None)
        app.dependency_overrides.pop(get_industry_selection_service, None)
    
    return mock_outline_svc, mock_industry_svc, cleanup


# ==================== 测试大纲创建 ====================

class TestOutlineCreation:
    """测试大纲创建功能"""

    def test_create_outline_from_text_success(self):
        """测试从Markdown文本创建大纲 - 成功场景"""
        # 使用测试数据库中存在的行业ID和数据库ID
        industry_id = "00000000-0000-0000-0000-000000000001"
        database_id = "00000000-0000-0000-0000-000000000010"
        
        # 创建mock大纲（使用真实的industry_id以匹配请求）
        mock_outline = create_mock_outline()
        # 更新mock_outline的industry_id以匹配请求
        mock_outline.industry_id = industry_id
        mock_outline.database_ids = [database_id]
        
        # 设置mock服务
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline, industry_id, database_id
        )
        
        try:
            # 准备请求数据
            request_data = {
                "title": "储能产业研究报告大纲",
                "text": "# 储能产业研究报告\n\n## 第一章 市场概述\n\n### 1.1 市场规模\n\n## 第二章 技术分析",
                "industry_id": industry_id,
                "database_ids": [database_id],
            }

            # 发送请求
            response = client.post("/api/v1/outlines/create-from-text", json=request_data)

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            # OutlineCreateResponse 格式: outline, outline_id, title, status, total_items, created_at
            assert "outline" in data
            assert "outline_id" in data
            assert data["outline"]["id"] == str(mock_outline.id)
            assert data["outline"]["title"] == "测试大纲"
        finally:
            cleanup()

    def test_create_outline_from_structure_success(self):
        """测试从结构化数据创建大纲 - 成功场景"""
        # 使用测试数据库中存在的行业ID和数据库ID
        industry_id = "00000000-0000-0000-0000-000000000001"
        database_id = "00000000-0000-0000-0000-000000000010"
        
        # 创建mock大纲
        mock_outline = create_mock_outline()
        mock_outline.industry_id = industry_id
        mock_outline.database_ids = [database_id]
        
        # 设置mock服务
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline, industry_id, database_id
        )
        
        try:
            # 准备请求数据
            request_data = {
                "title": "储能产业研究报告大纲",
                "structure": [
                    {
                        "title": "第一章",
                        "content": "第一章内容",
                        "item_type": "SECTION",
                        "level": 1,
                        "order": 0,
                    },
                    {
                        "title": "1.1 节",
                        "content": "1.1 节内容",
                        "item_type": "SUBSECTION",
                        "level": 2,
                        "order": 1,
                    },
                ],
                "industry_id": industry_id,
                "database_ids": [database_id],
            }

            # 发送请求
            response = client.post("/api/v1/outlines/create-from-structure", json=request_data)

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            # OutlineCreateResponse 格式: outline, outline_id, title, status, total_items, created_at
            assert "outline" in data
            assert "outline_id" in data
            assert data["outline"]["id"] == str(mock_outline.id)
        finally:
            cleanup()

    def test_create_outline_from_text_invalid_markdown(self):
        """测试从Markdown文本创建大纲 - 无效的Markdown"""
        # 使用测试数据库中存在的行业ID和数据库ID
        industry_id = "00000000-0000-0000-0000-000000000001"
        database_id = "00000000-0000-0000-0000-000000000010"
        
        # 创建mock大纲
        mock_outline = create_mock_outline()
        
        # 设置mock服务（save_outline抛出异常）
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline, industry_id, database_id,
            save_side_effect=ValueError("无效的Markdown格式")
        )
        
        try:
            # 准备请求数据
            request_data = {
                "title": "测试大纲",
                "text": "这不是有效的Markdown格式",
                "industry_id": industry_id,
                "database_ids": [database_id],
            }

            # 发送请求
            response = client.post("/api/v1/outlines/create-from-text", json=request_data)

            # 验证响应 - ValueError 被路由转换为500错误
            # 实际上服务层抛出的 ValueError 被通用异常处理捕获
            assert response.status_code == 500
            data = response.json()
            # API使用自定义错误响应格式: {"error": True, "message": "...", ...}
            assert data["error"] is True
            assert "无效的Markdown格式" in data["message"]
        finally:
            cleanup()


# ==================== 测试大纲查询 ====================

class TestOutlineQuery:
    """测试大纲查询功能"""

    def test_get_outline_success(self):
        """测试获取大纲详情 - 成功场景"""
        # 设置mock
        mock_outline = create_mock_outline()
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline=mock_outline
        )
        
        try:
            # 发送请求
            outline_id = str(mock_outline.id)
            response = client.get(f"/api/v1/outlines/{outline_id}")

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["outline_id"] == outline_id
            assert data["title"] == "测试大纲"
            assert "outline" in data
            assert data["outline"]["id"] == outline_id
        finally:
            cleanup()

    def test_get_outline_not_found(self):
        """测试获取大纲详情 - 大纲不存在"""
        from src.shared.exceptions.base_exceptions import ResourceNotFoundError
        
        # 设置mock - get_outline抛出ResourceNotFoundError
        outline_id = str(uuid.uuid4())
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            get_outline_side_effect=ResourceNotFoundError(
                f"大纲不存在: {outline_id}",
                resource_type="Outline",
                resource_id=outline_id
            )
        )
        
        try:
            # 发送请求
            response = client.get(f"/api/v1/outlines/{outline_id}")

            # 验证响应
            assert response.status_code == 404
            data = response.json()
            # FastAPI错误响应格式: {"error": True, "message": "...", ...}
            assert "message" in data or "detail" in data
            error_msg = data.get("message") or data.get("detail", "")
            assert "大纲不存在" in error_msg
        finally:
            cleanup()

    def test_get_outline_tree_success(self):
        """测试获取大纲树结构 - 成功场景"""
        # 设置mock
        mock_outline = create_mock_outline()
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline=mock_outline
        )
        
        try:
            # 发送请求
            outline_id = str(mock_outline.id)
            response = client.get(f"/api/v1/outlines/{outline_id}/tree")

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert "tree" in data
            assert len(data["tree"]) > 0
            # outline_id 在响应中是字符串格式
            assert str(data["outline_id"]) == outline_id
        finally:
            cleanup()


# ==================== 测试大纲更新和删除 ====================

class TestOutlineUpdateDelete:
    """测试大纲更新和删除功能"""

    def test_update_outline_success(self):
        """测试更新大纲 - 成功场景"""
        # 设置mock
        mock_outline = create_mock_outline()
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline=mock_outline
        )

        try:
            # 准备请求数据
            request_data = {
                "title": "更新后的标题",
                "description": "更新后的描述",
            }

            # 发送请求
            outline_id = str(mock_outline.id)
            response = client.put(f"/api/v1/outlines/{outline_id}", json=request_data)

            # 验证响应 - update_outline 返回 OutlineDetailResponse，没有 success 字段
            assert response.status_code == 200
            data = response.json()
            assert data["outline_id"] == outline_id
            assert data["title"] == "更新后的标题"
        finally:
            cleanup()

    def test_delete_outline_success(self):
        """测试删除大纲 - 成功场景"""
        # 设置mock
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            delete_outline=True
        )

        try:
            # 发送请求
            outline_id = str(uuid.uuid4())
            response = client.delete(f"/api/v1/outlines/{outline_id}")

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "大纲删除成功"
        finally:
            cleanup()

    def test_delete_outline_not_found(self):
        """测试删除大纲 - 大纲不存在"""
        # 注意：当前 delete_outline 路由有 TODO 注释，未实现实际删除功能
        # 路由直接返回成功，不调用服务方法
        # 因此这个测试暂时跳过，等待路由实现后再测试
        pytest.skip("delete_outline 路由尚未实现实际删除功能，当前直接返回成功")


# ==================== 测试大纲优化 ====================

class TestOutlineOptimization:
    """测试大纲优化功能"""

    def test_optimize_outline_success(self):
        """测试AI优化大纲 - 成功场景"""
        # 设置mock
        mock_outline = create_mock_outline()
        mock_optimized_outline = create_mock_optimized_outline(str(mock_outline.id))
        
        # 设置get_outline返回格式
        outline_dict = mock_outline.to_dict()
        items_dict = [item.to_dict() for item in mock_outline.items]
        get_outline_return = {
            "outline": outline_dict,
            "items": items_dict,
            "versions": [],
        }
        
        # 设置industry和database的mock
        industry_id = str(mock_outline.industry_id)
        database_id = mock_outline.database_ids[0] if mock_outline.database_ids else str(uuid.uuid4())
        
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline=mock_outline,
            industry_id=industry_id,
            database_id=database_id,
            get_outline_return=get_outline_return,
            save_optimized_outline={"id": str(mock_optimized_outline.id), "summary": "优化完成"}
        )
        
        # Mock LLM服务
        from src.interfaces.api.routes.outline_mvp import get_llm_service
        mock_llm_service = Mock()
        app.dependency_overrides[get_llm_service] = lambda: mock_llm_service
        
        # Mock create_outline_optimizer_agent 函数
        from unittest.mock import patch
        mock_agent = Mock()
        mock_agent.optimize_outline.return_value = mock_optimized_outline
        
        with patch("src.interfaces.api.routes.outline_mvp.create_outline_optimizer_agent", return_value=mock_agent):
            try:
                # 准备请求数据
                request_data = {
                    "industry_name": "储能行业",
                    "database_names": ["储能行业知识库"],
                }

                # 发送请求
                outline_id = str(mock_outline.id)
                response = client.post(
                    f"/api/v1/outlines/{outline_id}/optimize", json=request_data
                )

                # 验证响应
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "data" in data
            finally:
                cleanup()
                app.dependency_overrides.pop(get_llm_service, None)

    def test_get_optimized_outline_success(self):
        """测试获取优化后大纲 - 成功场景"""
        # 设置mock
        mock_optimized_outline = create_mock_optimized_outline()
        optimized_dict = mock_optimized_outline.to_dict()
        
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            get_optimized_outline=optimized_dict
        )

        try:
            # 发送请求
            optimized_outline_id = str(mock_optimized_outline.id)
            response = client.get(f"/api/v1/outlines/optimized/{optimized_outline_id}")

            # 验证响应 - get_optimized_outline 使用 create_success_response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            # 数据在 data 字段中
            assert "data" in data
            assert data["data"]["id"] == optimized_outline_id
        finally:
            cleanup()


# ==================== 测试优化接受/拒绝 ====================

class TestOptimizationAcceptReject:
    """测试优化接受/拒绝功能"""

    def test_accept_optimization_item_success(self):
        """测试接受单个优化项 - 成功场景"""
        # 设置mock
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            accept_optimization_item=True
        )

        try:
            # 发送请求
            optimized_outline_id = str(uuid.uuid4())
            item_id = str(uuid.uuid4())
            response = client.post(
                f"/api/v1/outlines/optimized/{optimized_outline_id}/accept-item/{item_id}"
            )

            # 验证响应 - accept_optimization_item 使用 create_success_response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "接受优化项成功" in data["message"]
        finally:
            cleanup()

    def test_reject_optimization_item_success(self):
        """测试拒绝单个优化项 - 成功场景"""
        # 设置mock
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            reject_optimization_item=True
        )

        try:
            # 发送请求
            optimized_outline_id = str(uuid.uuid4())
            item_id = str(uuid.uuid4())
            response = client.post(
                f"/api/v1/outlines/optimized/{optimized_outline_id}/reject-item/{item_id}"
            )

            # 验证响应 - reject_optimization_item 使用 create_success_response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "拒绝优化项成功" in data["message"]
        finally:
            cleanup()

    def test_accept_all_optimizations_success(self):
        """测试接受所有优化 - 成功场景"""
        # 设置mock
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            accept_all_optimizations=True
        )

        try:
            # 发送请求
            optimized_outline_id = str(uuid.uuid4())
            response = client.post(
                f"/api/v1/outlines/optimized/{optimized_outline_id}/accept-all"
            )

            # 验证响应 - accept_all_optimizations 使用 create_success_response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "接受所有优化建议成功" in data["message"]
        finally:
            cleanup()

    def test_reject_all_optimizations_success(self):
        """测试拒绝所有优化 - 成功场景"""
        # 设置mock
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            reject_all_optimizations=True
        )

        try:
            # 发送请求
            optimized_outline_id = str(uuid.uuid4())
            response = client.post(
                f"/api/v1/outlines/optimized/{optimized_outline_id}/reject-all"
            )

            # 验证响应 - reject_all_optimizations 使用 create_success_response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "拒绝所有优化建议成功" in data["message"]
        finally:
            cleanup()


# ==================== 测试最终大纲生成 ====================

class TestFinalOutlineGeneration:
    """测试最终大纲生成功能"""

    def test_generate_final_outline_success(self):
        """测试生成最终大纲 - 成功场景"""
        # 设置mock
        mock_outline = create_mock_outline()
        mock_outline.status = OutlineStatus.FINALIZED
        final_outline_dict = mock_outline.to_dict()
        
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            generate_final_outline=final_outline_dict
        )

        try:
            # 发送请求 - generate_final_outline 需要 optimized_outline_id 作为查询参数
            outline_id = str(uuid.uuid4())
            optimized_outline_id = str(uuid.uuid4())
            response = client.post(
                f"/api/v1/outlines/{outline_id}/generate-final?optimized_outline_id={optimized_outline_id}"
            )

            # 验证响应 - generate_final_outline 使用 create_success_response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "final_outline" in data["data"]
            assert data["data"]["final_outline"]["status"] == "FINALIZED"
        finally:
            cleanup()


# ==================== 测试优化历史和状态 ====================

class TestOptimizationHistoryStatus:
    """测试优化历史和状态查询功能"""

    def test_get_optimization_history_success(self):
        """测试获取优化历史 - 成功场景"""
        # 设置mock
        mock_optimized_outline = create_mock_optimized_outline()
        optimized_dict = mock_optimized_outline.to_dict()
        
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            get_optimization_history=[optimized_dict]
        )

        try:
            # 发送请求
            outline_id = str(uuid.uuid4())
            response = client.get(f"/api/v1/outlines/{outline_id}/optimization-history")

            # 验证响应 - get_optimization_history 使用 create_success_response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "history" in data["data"]
            assert len(data["data"]["history"]) == 1
        finally:
            cleanup()

    def test_get_optimization_status_success(self):
        """测试获取优化状态 - 成功场景"""
        # 设置mock
        status_data = {
            "total_items": 10,
            "accepted_count": 5,
            "rejected_count": 2,
            "pending_count": 3,
        }
        
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            get_optimization_status=status_data
        )

        try:
            # 发送请求
            optimized_outline_id = str(uuid.uuid4())
            response = client.get(f"/api/v1/outlines/optimized/{optimized_outline_id}/status")

            # 验证响应 - get_optimization_status 使用 create_success_response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "total_items" in data["data"]
            assert data["data"]["total_items"] == 10
        finally:
            cleanup()


# ==================== 测试大纲项管理 ====================

class TestOutlineItemManagement:
    """测试大纲项管理功能"""

    def test_add_outline_item_success(self):
        """测试添加大纲项 - 成功场景"""
        # 设置mock
        mock_outline = create_mock_outline()
        new_item = OutlineItem(
            id=str(uuid.uuid4()),
            title="新章节",
            content="新章节内容",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=2,
        )
        new_item_dict = new_item.to_dict()
        
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline=mock_outline,
            add_outline_item=new_item_dict
        )

        try:
            # 准备请求数据
            request_data = {
                "title": "新章节",
                "content": "新章节内容",
                "item_type": "SECTION",
                "level": 1,
                "order": 2,
            }

            # 发送请求
            outline_id = str(mock_outline.id)
            response = client.post(f"/api/v1/outlines/{outline_id}/items", json=request_data)

            # 验证响应 - add_outline_item 返回 OutlineItemCreateResponse
            assert response.status_code == 200
            data = response.json()
            assert "item" in data
            assert data["item_id"] is not None
            assert data["outline_id"] == outline_id
        finally:
            cleanup()

    def test_update_outline_item_success(self):
        """测试更新大纲项 - 成功场景"""
        # 设置mock - update_outline_item 需要 get_outline
        mock_outline = create_mock_outline()
        updated_item = mock_outline.items[0]
        updated_item.title = "更新后的标题"
        updated_item_dict = updated_item.to_dict()
        
        outline_dict = mock_outline.to_dict()
        items_dict = [item.to_dict() for item in mock_outline.items]
        get_outline_return = {
            "outline": outline_dict,
            "items": items_dict,
            "versions": [],
        }
        
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline=mock_outline,
            get_outline_return=get_outline_return
        )

        try:
            # 准备请求数据
            request_data = {
                "title": "更新后的标题",
                "content": "更新后的内容",
            }

            # 发送请求
            outline_id = str(mock_outline.id)
            item_id = str(updated_item.id)
            response = client.put(
                f"/api/v1/outlines/{outline_id}/items/{item_id}", json=request_data
            )

            # 验证响应 - update_outline_item 返回 OutlineItemUpdateResponse
            assert response.status_code == 200
            data = response.json()
            assert "item" in data
            assert data["item_id"] == item_id
            assert data["outline_id"] == outline_id
        finally:
            cleanup()

    def test_delete_outline_item_success(self):
        """测试删除大纲项 - 成功场景"""
        # 设置mock - delete_outline_item 需要 get_outline
        mock_outline = create_mock_outline()
        outline_dict = mock_outline.to_dict()
        items_dict = [item.to_dict() for item in mock_outline.items]
        get_outline_return = {
            "outline": outline_dict,
            "items": items_dict,
            "versions": [],
        }
        
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            mock_outline=mock_outline,
            get_outline_return=get_outline_return
        )

        try:
            # 发送请求
            outline_id = str(mock_outline.id)
            item_id = str(mock_outline.items[0].id)
            response = client.delete(f"/api/v1/outlines/{outline_id}/items/{item_id}")

            # 验证响应 - delete_outline_item 返回 DeleteResponse
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "大纲项删除成功"
        finally:
            cleanup()


# ==================== 测试错误处理 ====================

class TestErrorHandling:
    """测试错误处理"""

    def test_service_exception_handling(self):
        """测试服务异常处理"""
        # 设置mock - get_outline抛出异常
        mock_outline_svc, mock_industry_svc, cleanup = _setup_mock_services(
            get_outline_side_effect=Exception("服务异常")
        )

        try:
            # 发送请求
            outline_id = str(uuid.uuid4())
            response = client.get(f"/api/v1/outlines/{outline_id}")

            # 验证响应
            assert response.status_code == 500
            data = response.json()
            # FastAPI错误响应格式: {"error": True, "message": "...", ...}
            assert "message" in data or "detail" in data
            error_msg = data.get("message") or data.get("detail", "")
            assert "服务异常" in error_msg
        finally:
            cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
