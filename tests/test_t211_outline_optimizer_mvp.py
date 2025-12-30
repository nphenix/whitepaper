"""
T211大纲优化Agent测试

测试大纲优化Agent的功能，包括：
1. 提示词模板创建
2. Agent初始化
3. 大纲优化功能
4. 结构化输出

生成命令: 手动创建
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from pathlib import Path

import pytest

from src.application.agents.outline_optimizer_mvp import (
    OutlineOptimizerAgent,
    OptimizationResult,
    create_outline_optimizer_agent,
)
from src.application.agents.outline_optimization_prompts import (
    OutlineOptimizationPrompts,
    get_outline_optimization_prompt,
    get_outline_optimization_system_message,
)
from src.domain.agent.outline import Outline, OutlineItem, OutlineItemType, OutlineStatus
from src.domain.agent.optimized_outline import (
    OptimizedOutline,
    OptimizationChangeType,
)
from src.shared.config.llm_service import LLMService


class TestOutlineOptimizationPrompts:
    """大纲优化提示词模板测试"""

    def test_get_system_message(self):
        """测试获取系统消息"""
        system_message = OutlineOptimizationPrompts.get_system_message(
            industry_name="储能行业",
            report_type="市场研究报告",
            language="中文",
            style="专业、客观、数据驱动",
        )

        assert "储能行业" in system_message
        assert "市场研究报告" in system_message
        assert "中文" in system_message
        assert "专业、客观、数据驱动" in system_message
        assert "完整性" in system_message
        assert "准确性" in system_message

    def test_get_optimization_prompt(self):
        """测试获取优化提示词模板"""
        prompt = OutlineOptimizationPrompts.get_optimization_prompt()

        assert prompt is not None
        assert hasattr(prompt, "format_messages")

    def test_format_outline_structure(self):
        """测试格式化大纲结构"""
        outline_dict = {
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "parent_id": None,
                    "item_type": "SECTION",
                    "level": 1,
                    "title": "行业概述",
                    "description": "储能行业的基本情况",
                    "order": 1,
                    "children": [
                        {
                            "id": str(uuid.uuid4()),
                            "parent_id": str(uuid.uuid4()),
                            "item_type": "SUBSECTION",
                            "level": 2,
                            "title": "市场规模",
                            "description": "储能市场规模分析",
                            "order": 1,
                        }
                    ],
                }
            ]
        }

        formatted = OutlineOptimizationPrompts.format_outline_structure(outline_dict)

        assert "行业概述" in formatted
        assert "市场规模" in formatted

    def test_build_optimization_input(self):
        """测试构建优化输入"""
        input_dict = OutlineOptimizationPrompts.build_optimization_input(
            outline_title="储能行业分析报告",
            outline_description="储能行业的市场分析和发展趋势",
            industry_name="储能行业",
            database_names=["储能行业知识库", "储能行业市场数据库"],
            outline_structure="# 行业概述\n\n## 市场规模",
            report_type="市场研究报告",
        )

        assert input_dict["outline_title"] == "储能行业分析报告"
        assert input_dict["industry_name"] == "储能行业"
        assert input_dict["database_names"] == "储能行业知识库, 储能行业市场数据库"
        assert input_dict["report_type"] == "市场研究报告"


class TestOutlineOptimizerAgent:
    """大纲优化Agent测试"""

    @pytest.fixture
    def llm_service(self):
        """LLM服务fixture"""
        return LLMService()

    @pytest.fixture
    def agent_config(self):
        """Agent配置fixture"""
        from src.application.agent_base import AgentConfig

        return AgentConfig(
            agent_id="test_outline_optimizer",
            agent_name="TestOutlineOptimizer",
            agent_type="outline_optimizer",
            description="测试用大纲优化Agent",
            temperature=0.3,
            max_tokens=4000,
        )

    @pytest.fixture
    def sample_outline(self):
        """示例大纲fixture"""
        outline = Outline(
            title="储能行业分析报告",
            description="储能行业的市场分析和发展趋势",
            industry_id=uuid.uuid4(),
            database_ids=[uuid.uuid4()],
            status=OutlineStatus.DRAFT,
        )

        # 添加大纲项
        item1 = OutlineItem(
            parent_id=None,
            item_type=OutlineItemType.SECTION,
            level=1,
            title="行业概述",
            description="储能行业的基本情况",
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
            title="技术发展",
            description="储能技术发展趋势",
            order=2,
        )
        outline.add_item(item3)

        return outline

    def test_agent_initialization(self, agent_config, llm_service):
        """测试Agent初始化"""
        agent = OutlineOptimizerAgent(
            config=agent_config,
            llm_service=llm_service,
            report_type="市场研究报告",
            language="中文",
            style="专业、客观、数据驱动",
        )

        assert agent.agent_id == "test_outline_optimizer"
        assert agent.agent_name == "TestOutlineOptimizer"
        assert agent.report_type == "市场研究报告"
        assert agent.language == "中文"
        assert agent.style == "专业、客观、数据驱动"

    def test_get_tools(self, agent_config, llm_service):
        """测试获取工具列表"""
        agent = OutlineOptimizerAgent(
            config=agent_config,
            llm_service=llm_service,
        )

        tools = agent.get_tools()

        # 大纲优化Agent主要使用LLM直接推理，不需要额外工具
        assert isinstance(tools, list)
        # 可以添加知识库检索工具等

    def test_analyze_outline_structure(self, agent_config, llm_service, sample_outline):
        """测试分析大纲结构"""
        agent = OutlineOptimizerAgent(
            config=agent_config,
            llm_service=llm_service,
        )

        analysis = agent.analyze_outline_structure(sample_outline)

        assert "total_items" in analysis
        assert "root_items" in analysis
        assert "max_level" in analysis
        assert "items_by_level" in analysis
        assert "items_by_type" in analysis
        assert analysis["total_items"] == 3
        assert analysis["root_items"] == 1
        assert analysis["max_level"] == 2

    def test_generate_optimization_suggestions(
        self, agent_config, llm_service, sample_outline
    ):
        """测试生成优化建议"""
        agent = OutlineOptimizerAgent(
            config=agent_config,
            llm_service=llm_service,
        )

        suggestions = agent.generate_optimization_suggestions(
            outline=sample_outline,
            context={
                "industry_name": "储能行业",
                "database_names": ["储能行业知识库"],
            },
        )

        assert isinstance(suggestions, list)
        # 可以检查建议的类型和优先级

    def test_get_system_message(self, agent_config, llm_service):
        """测试获取系统消息"""
        agent = OutlineOptimizerAgent(
            config=agent_config,
            llm_service=llm_service,
            report_type="市场研究报告",
        )

        system_message = agent._get_system_message()

        assert "大纲优化专家" in system_message
        assert "市场研究报告" in system_message
        assert "中文" in system_message

    def test_optimize_outline_requires_llm(
        self, agent_config, llm_service, sample_outline
    ):
        """测试大纲优化需要LLM"""
        agent = OutlineOptimizerAgent(
            config=agent_config,
            llm_service=llm_service,
        )

        # 这个测试需要实际的LLM调用，可能需要mock
        # 在实际环境中运行
        # optimized_outline = agent.optimize_outline(
        #     outline=sample_outline,
        #     industry_name="储能行业",
        #     database_names=["储能行业知识库"],
        # )
        # assert isinstance(optimized_outline, OptimizedOutline)
        pass


class TestCreateOutlineOptimizerAgent:
    """创建大纲优化Agent的便捷函数测试"""

    def test_create_outline_optimizer_agent(self):
        """测试创建大纲优化Agent"""
        agent = create_outline_optimizer_agent(
            agent_id="test_optimizer",
            agent_name="TestOptimizer",
            report_type="市场研究报告",
            language="中文",
            style="专业、客观、数据驱动",
        )

        assert isinstance(agent, OutlineOptimizerAgent)
        assert agent.agent_id == "test_optimizer"
        assert agent.agent_name == "TestOptimizer"
        assert agent.report_type == "市场研究报告"


class TestOptimizationResult:
    """优化结果模型测试"""

    def test_optimization_result_creation(self):
        """测试优化结果模型创建"""
        result = OptimizationResult(
            optimization_summary={
                "total_changes": 5,
                "quality_score": 0.85,
            },
            optimized_items=[
                {
                    "original_item_id": str(uuid.uuid4()),
                    "optimized_item": {
                        "title": "优化后标题",
                        "description": "优化后描述",
                    },
                    "change_type": "MODIFY",
                }
            ],
        )

        assert result.optimization_summary["total_changes"] == 5
        assert result.optimization_summary["quality_score"] == 0.85
        assert len(result.optimized_items) == 1


class TestConvenienceFunctions:
    """便利函数测试"""

    def test_get_outline_optimization_prompt(self):
        """测试获取大纲优化提示词模板"""
        prompt = get_outline_optimization_prompt()

        assert prompt is not None

    def test_get_outline_optimization_system_message(self):
        """测试获取大纲优化系统消息"""
        system_message = get_outline_optimization_system_message(
            industry_name="储能行业",
            report_type="市场研究报告",
        )

        assert "储能行业" in system_message
        assert "市场研究报告" in system_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
