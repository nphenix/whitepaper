"""
Mock数据检测工具

用于检测前端是否使用了mock数据而不是真实API数据。
"""

from typing import List, Dict, Any


# 前端mock数据的特征标识
MOCK_DATA_INDICATORS = {
    "final_view": [
        "未来五年储能产业政策与发展趋势白皮书",  # mock数据的标题
        "美国《通胀削减法案》(IRA)",  # mock数据的特定内容
        "彭博新能源财经(BNEF)",  # mock数据的特定内容
        "国家能源局发布的《新型储能发展实施方案(2024-2027)》",  # mock数据的特定内容
    ],
    "source_selection": [
        "Global Energy Storage Policy Landscape 2024—Comparative Review",  # mock推荐来源
        "The Role of Energy Storage in Carbon Neutrality Strategies",  # mock推荐来源
        '"新型储能"政策体系建设与市场化机制研究',  # mock推荐来源
    ],
}


def is_mock_data(content: str, data_type: str = "final_view") -> bool:
    """检测内容是否是mock数据
    
    Args:
        content: 要检测的内容
        data_type: 数据类型（"final_view"或"source_selection"）
    
    Returns:
        bool: 如果是mock数据返回True，否则返回False
    """
    if data_type not in MOCK_DATA_INDICATORS:
        return False
    
    indicators = MOCK_DATA_INDICATORS[data_type]
    return any(indicator in content for indicator in indicators)


def detect_mock_data_in_draft(draft_content: str) -> Dict[str, Any]:
    """检测草稿内容是否是mock数据
    
    Args:
        draft_content: 草稿内容
    
    Returns:
        dict: 包含检测结果的字典
    """
    is_mock = is_mock_data(draft_content, "final_view")
    
    result = {
        "is_mock": is_mock,
        "indicators_found": [],
    }
    
    if is_mock:
        indicators = MOCK_DATA_INDICATORS["final_view"]
        found = [ind for ind in indicators if ind in draft_content]
        result["indicators_found"] = found
    
    return result


def detect_mock_data_in_sources(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """检测推荐来源是否是mock数据
    
    Args:
        sources: 推荐来源列表
    
    Returns:
        dict: 包含检测结果的字典
    """
    if not sources:
        return {"is_mock": False, "reason": "没有来源数据"}
    
    # 检查来源标题是否包含mock数据的特征
    titles = [s.get("title", "") for s in sources]
    all_titles = " ".join(titles)
    
    is_mock = is_mock_data(all_titles, "source_selection")
    
    result = {
        "is_mock": is_mock,
        "indicators_found": [],
    }
    
    if is_mock:
        indicators = MOCK_DATA_INDICATORS["source_selection"]
        found = [ind for ind in indicators if ind in all_titles]
        result["indicators_found"] = found
    
    return result


def validate_not_mock_data(content: str, data_type: str = "final_view", context: str = "") -> None:
    """验证内容不是mock数据，如果是则抛出异常
    
    Args:
        content: 要验证的内容
        data_type: 数据类型
        context: 上下文信息（用于错误消息）
    
    Raises:
        AssertionError: 如果检测到mock数据
    """
    if is_mock_data(content, data_type):
        indicators = MOCK_DATA_INDICATORS.get(data_type, [])
        found = [ind for ind in indicators if ind in content]
        
        error_msg = (
            f"检测到mock数据！{context}\n"
            f"内容应该是从API获取的真实数据，而不是前端mock数据。\n"
            f"如果看到此错误，说明API调用失败，前端降级到了mock数据。\n"
            f"检测到的mock标识: {found}\n"
            f"内容预览: {content[:200]}..."
        )
        raise AssertionError(error_msg)
