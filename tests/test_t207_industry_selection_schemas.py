"""
T207: 行业选择Schema测试

测试行业选择相关的Schema定义和功能。
"""

# 生成命令: /speckit.implement T207
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import pytest
from uuid import uuid4
from typing import List

from src.interfaces.api.schemas.industry_selection_schemas import (
    SortOrder,
    SortBy,
    IndustryListRequest,
    IndustryDetailRequest,
    IndustryDatabaseListRequest,
    DatabaseDetailRequest,
    IndustrySelectionRequest,
    IndustrySelectionUpdateRequest,
    IndustrySelectionDetailRequest,
    IndustrySelectionListRequest,
    IndustryStatisticsRequest,
    IndustryValidationRequest,
    IndustryResponse,
    DatabaseResponse,
    IndustryListResponse,
    DatabaseListResponse,
    IndustrySelectionResponse,
    IndustrySelectionListResponse,
    IndustryValidationResponse,
    IndustryStatisticsResponse,
    SuccessResponse,
    DeleteResponse,
    IndustrySelectionRequestValidator,
    IndustrySelectionUpdateRequestValidator,
    create_industry_response,
    create_database_response,
    create_success_response,
    create_error_response,
)


class TestIndustrySelectionSchemas:
    """测试行业选择Schema"""

    def test_sort_order_enum(self):
        """测试排序方向枚举"""
        assert SortOrder.ASC.value == "asc"
        assert SortOrder.DESC.value == "desc"
        assert len(SortOrder) == 2

    def test_sort_by_enum(self):
        """测试排序字段枚举"""
        assert SortBy.NAME.value == "name"
        assert SortBy.CODE.value == "code"
        assert SortBy.CREATED_AT.value == "created_at"
        assert len(SortBy) == 3

    def test_industry_list_request(self):
        """测试行业列表请求"""
        # 测试默认值
        request = IndustryListRequest()
        assert request.sort_by == SortBy.NAME
        assert request.sort_order == SortOrder.ASC
        assert request.skip == 0
        assert request.limit == 100

        # 测试自定义值
        request = IndustryListRequest(
            sort_by=SortBy.CODE,
            sort_order=SortOrder.DESC,
            skip=10,
            limit=50
        )
        assert request.sort_by == SortBy.CODE
        assert request.sort_order == SortOrder.DESC
        assert request.skip == 10
        assert request.limit == 50

    def test_industry_detail_request(self):
        """测试行业详情请求"""
        industry_id = uuid4()
        request = IndustryDetailRequest(industry_id=industry_id)
        assert request.industry_id == industry_id

    def test_industry_database_list_request(self):
        """测试行业数据库列表请求"""
        industry_id = uuid4()
        request = IndustryDatabaseListRequest(
            industry_id=industry_id,
            sort_by=SortBy.NAME,
            sort_order=SortOrder.DESC,
            skip=5,
            limit=20
        )
        assert request.industry_id == industry_id
        assert request.sort_by == SortBy.NAME
        assert request.sort_order == SortOrder.DESC
        assert request.skip == 5
        assert request.limit == 20

    def test_database_detail_request(self):
        """测试数据库详情请求"""
        database_id = uuid4()
        request = DatabaseDetailRequest(database_id=database_id)
        assert request.database_id == database_id

    def test_industry_selection_request(self):
        """测试行业选择请求"""
        industry_id = uuid4()
        database_ids = [uuid4(), uuid4()]
        request = IndustrySelectionRequest(
            industry_id=industry_id,
            database_ids=database_ids,
            user_id="test_user"
        )
        assert request.industry_id == industry_id
        assert request.database_ids == database_ids
        assert request.user_id == "test_user"

    def test_industry_selection_update_request(self):
        """测试行业选择更新请求"""
        selection_id = uuid4()
        database_ids = [uuid4(), uuid4()]
        request = IndustrySelectionUpdateRequest(
            selection_id=selection_id,
            database_ids=database_ids
        )
        assert request.selection_id == selection_id
        assert request.database_ids == database_ids

    def test_industry_selection_detail_request(self):
        """测试行业选择详情请求"""
        selection_id = uuid4()
        request = IndustrySelectionDetailRequest(selection_id=selection_id)
        assert request.selection_id == selection_id

    def test_industry_selection_list_request(self):
        """测试行业选择列表请求"""
        request = IndustrySelectionListRequest(
            user_id="test_user",
            skip=10,
            limit=50
        )
        assert request.user_id == "test_user"
        assert request.skip == 10
        assert request.limit == 50

    def test_industry_statistics_request(self):
        """测试行业统计请求"""
        request = IndustryStatisticsRequest()
        assert request.include_database_counts is True

        request = IndustryStatisticsRequest(include_database_counts=False)
        assert request.include_database_counts is False

    def test_industry_validation_request(self):
        """测试行业验证请求"""
        request = IndustryValidationRequest(
            industry_code="TECH",
            database_codes=["DB1", "DB2"]
        )
        assert request.industry_code == "TECH"
        assert request.database_codes == ["DB1", "DB2"]

    def test_industry_response(self):
        """测试行业响应"""
        industry_id = uuid4()
        response = IndustryResponse(
            id=industry_id,
            name="Technology",
            code="TECH",
            category="Technology",
            description="Technology industry",
            is_active=True
        )
        assert response.id == industry_id
        assert response.name == "Technology"
        assert response.code == "TECH"
        assert response.category == "Technology"
        assert response.description == "Technology industry"
        assert response.is_active is True

    def test_database_response(self):
        """测试数据库响应"""
        database_id = uuid4()
        industry_id = uuid4()
        response = DatabaseResponse(
            id=database_id,
            name="Tech Database",
            code="TECH_DB",
            industry_id=industry_id,
            database_type="knowledge_graph",
            data_source="manual",
            description="Technology knowledge database",
            is_active=True,
            document_count=100
        )
        assert response.id == database_id
        assert response.name == "Tech Database"
        assert response.code == "TECH_DB"
        assert response.industry_id == industry_id
        assert response.database_type == "knowledge_graph"
        assert response.data_source == "manual"
        assert response.description == "Technology knowledge database"
        assert response.is_active is True
        assert response.document_count == 100

    def test_industry_list_response(self):
        """测试行业列表响应"""
        industries = [
            IndustryResponse(
                id=uuid4(),
                name="Technology",
                code="TECH",
                category="Technology",
                description="Technology industry",
                is_active=True
            ),
            IndustryResponse(
                id=uuid4(),
                name="Finance",
                code="FIN",
                category="Finance",
                description="Finance industry",
                is_active=True
            )
        ]
        response = IndustryListResponse(
            industries=industries,
            total=2,
            skip=0,
            limit=100
        )
        assert len(response.industries) == 2
        assert response.total == 2
        assert response.skip == 0
        assert response.limit == 100

    def test_database_list_response(self):
        """测试数据库列表响应"""
        databases = [
            DatabaseResponse(
                id=uuid4(),
                name="Tech Database",
                code="TECH_DB",
                industry_id=uuid4(),
                database_type="knowledge_graph",
                data_source="manual",
                description="Technology knowledge database",
                is_active=True,
                document_count=100
            )
        ]
        response = DatabaseListResponse(
            databases=databases,
            total=1,
            skip=0,
            limit=100
        )
        assert len(response.databases) == 1
        assert response.total == 1
        assert response.skip == 0
        assert response.limit == 100

    def test_industry_selection_response(self):
        """测试行业选择响应"""
        selection_id = uuid4()
        industry_id = uuid4()
        database_ids = [uuid4(), uuid4()]
        response = IndustrySelectionResponse(
            id=selection_id,
            industry_id=industry_id,
            database_ids=database_ids,
            user_id="test_user",
            is_active=True
        )
        assert response.id == selection_id
        assert response.industry_id == industry_id
        assert response.database_ids == database_ids
        assert response.user_id == "test_user"
        assert response.is_active is True

    def test_industry_selection_list_response(self):
        """测试行业选择列表响应"""
        selections = [
            IndustrySelectionResponse(
                id=uuid4(),
                industry_id=uuid4(),
                database_ids=[uuid4()],
                user_id="test_user",
                is_active=True
            )
        ]
        response = IndustrySelectionListResponse(
            selections=selections,
            total=1,
            skip=0,
            limit=100
        )
        assert len(response.selections) == 1
        assert response.total == 1
        assert response.skip == 0
        assert response.limit == 100

    def test_industry_validation_response(self):
        """测试行业验证响应"""
        response = IndustryValidationResponse(
            industry_code="TECH",
            is_valid=True,
            industry_name="Technology",
            database_validations=[
                {
                    "database_code": "DB1",
                    "is_valid": True,
                    "database_name": "Database 1"
                }
            ]
        )
        assert response.industry_code == "TECH"
        assert response.is_valid is True
        assert response.industry_name == "Technology"
        assert len(response.database_validations) == 1

    def test_industry_statistics_response(self):
        """测试行业统计响应"""
        response = IndustryStatisticsResponse(
            total_industries=10,
            active_industries=8,
            total_databases=25,
            active_databases=20,
            database_counts_by_type={"knowledge_graph": 15, "vector": 10},
            database_counts_by_source={"manual": 12, "automated": 13}
        )
        assert response.total_industries == 10
        assert response.active_industries == 8
        assert response.total_databases == 25
        assert response.active_databases == 20
        assert response.database_counts_by_type["knowledge_graph"] == 15
        assert response.database_counts_by_source["manual"] == 12

    def test_success_response(self):
        """测试成功响应"""
        response = SuccessResponse(
            success=True,
            message="Operation completed successfully"
        )
        assert response.success is True
        assert response.message == "Operation completed successfully"

    def test_delete_response(self):
        """测试删除响应"""
        response = DeleteResponse(
            success=True,
            message="Industry selection deleted successfully"
        )
        assert response.success is True
        assert response.message == "Industry selection deleted successfully"

    def test_industry_selection_request_validator(self):
        """测试行业选择请求验证器"""
        # 测试有效请求
        industry_id = uuid4()
        database_ids = [uuid4(), uuid4()]
        request = IndustrySelectionRequest(
            industry_id=industry_id,
            database_ids=database_ids,
            user_id="test_user"
        )
        
        validator = IndustrySelectionRequestValidator()
        assert validator.validate(request) is True
        
        # 测试无效请求（空database_ids）
        invalid_request = IndustrySelectionRequest(
            industry_id=industry_id,
            database_ids=[],
            user_id="test_user"
        )
        
        assert validator.validate(invalid_request) is False

    def test_industry_selection_update_request_validator(self):
        """测试行业选择更新请求验证器"""
        # 测试有效请求
        selection_id = uuid4()
        database_ids = [uuid4(), uuid4()]
        request = IndustrySelectionUpdateRequest(
            selection_id=selection_id,
            database_ids=database_ids
        )
        
        validator = IndustrySelectionUpdateRequestValidator()
        assert validator.validate(request) is True
        
        # 测试无效请求（空database_ids）
        invalid_request = IndustrySelectionUpdateRequest(
            selection_id=selection_id,
            database_ids=[]
        )
        
        assert validator.validate(invalid_request) is False

    def test_create_industry_response(self):
        """测试创建行业响应辅助函数"""
        industry_id = uuid4()
        response = create_industry_response(
            industry_id=industry_id,
            name="Technology",
            code="TECH",
            category="Technology",
            description="Technology industry"
        )
        assert response.id == industry_id
        assert response.name == "Technology"
        assert response.code == "TECH"
        assert response.category == "Technology"
        assert response.description == "Technology industry"
        assert response.is_active is True

    def test_create_database_response(self):
        """测试创建数据库响应辅助函数"""
        database_id = uuid4()
        industry_id = uuid4()
        response = create_database_response(
            database_id=database_id,
            name="Tech Database",
            code="TECH_DB",
            industry_id=industry_id,
            database_type="knowledge_graph",
            data_source="manual",
            description="Technology knowledge database"
        )
        assert response.id == database_id
        assert response.name == "Tech Database"
        assert response.code == "TECH_DB"
        assert response.industry_id == industry_id
        assert response.database_type == "knowledge_graph"
        assert response.data_source == "manual"
        assert response.description == "Technology knowledge database"
        assert response.is_active is True
        assert response.document_count == 0

    def test_create_success_response(self):
        """测试创建成功响应辅助函数"""
        response = create_success_response("Operation completed")
        assert response.success is True
        assert response.message == "Operation completed"

    def test_create_error_response(self):
        """测试创建错误响应辅助函数"""
        response = create_error_response("Error occurred")
        assert response.success is False
        assert response.message == "Error occurred"


if __name__ == "__main__":
    pytest.main([__file__])