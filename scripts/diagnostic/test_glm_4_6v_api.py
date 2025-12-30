"""
GLM-4.6V API 调用验证脚本

用于验证 GLM-4.6V API 的正确调用方式，测试 LLMService 的 get_chart_to_json_chat_model 方法。
"""

import base64
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from openai import OpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.shared.config.llm_service import get_llm_service
from src.shared.config.settings import load_config


def test_direct_openai_sdk(base_url: str, api_key: str, model_name: str, image_path: str):
    """方法1: 直接使用 OpenAI SDK（最原始的方式）"""
    print("\n" + "="*80)
    print("方法1: 直接使用 OpenAI SDK")
    print("="*80)
    
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=120.0,
    )
    
    # 准备图像数据
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    
    mime_type = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    
    # 构建消息（OpenAI 标准格式）
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的图表分析助手。请分析这张图片中的图表，并将其转换为结构化的JSON格式。"
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请分析这张图片，判断它是否为图表，并提供详细的分析结果。请以JSON格式输出。"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_data}"
                    }
                }
            ]
        }
    ]
    
    print(f"Base URL: {base_url}")
    print(f"Model: {model_name}")
    print(f"Messages count: {len(messages)}")
    print(f"User message content type: {type(messages[1]['content'])}")
    print(f"Image URL format: {type(messages[1]['content'][1]['image_url'])}")
    print(f"Image URL length: {len(messages[1]['content'][1]['image_url']['url'])}")
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.1,
            max_tokens=56000,  # 进一步测试 56000 (56k)
        )
        
        print("\n✅ 调用成功!")
        print(f"Response: {response.choices[0].message.content[:200]}...")
        return True, response
    except Exception as e:
        print(f"\n❌ 调用失败: {type(e).__name__}: {e}")
        return False, str(e)


# 方法2已移除，因为 thinking 参数不被支持



def test_openai_sdk_adapter(base_url: str, api_key: str, model_name: str, image_path: str):
    """方法3: 使用 OpenAISDKAdapter（当前实现）"""
    print("\n" + "="*80)
    print("方法3: 使用 OpenAISDKAdapter（当前实现）")
    print("="*80)
    
    from src.shared.config.openai_sdk_adapter import OpenAISDKAdapter
    
    # 创建适配器
    model = OpenAISDKAdapter(
        model_name=model_name,
        temperature=0.1,
        max_tokens=56000,  # 进一步测试 56000 (56k)
        api_key=api_key,
        base_url=base_url,
        timeout=120.0,
    )
    
    # 准备图像数据
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    
    mime_type = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    
    # 构建 LangChain 消息格式
    messages = [
        SystemMessage(content="你是一个专业的图表分析助手。请分析这张图片中的图表，并将其转换为结构化的JSON格式。"),
        HumanMessage(content=[
            {
                "type": "text",
                "text": "请分析这张图片，判断它是否为图表，并提供详细的分析结果。请以JSON格式输出。"
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_data}"
                }
            }
        ])
    ]
    
    print(f"Base URL: {base_url}")
    print(f"Model: {model_name}")
    print(f"Messages count: {len(messages)}")
    
    try:
        response = model.invoke(messages)
        
        print("\n✅ 调用成功!")
        print(f"Response type: {type(response)}")
        if hasattr(response, 'content'):
            print(f"Response content: {response.content[:200]}...")
        else:
            print(f"Response: {str(response)[:200]}...")
        return True, response
    except Exception as e:
        print(f"\n❌ 调用失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def test_llm_service_chart_to_json(base_url: str, api_key: str, model_name: str, image_path: str):
    """方法4: 使用 LLMService 的 get_chart_to_json_chat_model（完整流程）"""
    print("\n" + "="*80)
    print("方法4: 使用 LLMService 的 get_chart_to_json_chat_model（完整流程）")
    print("="*80)
    
    # 加载配置
    config = load_config()
    
    # 设置环境变量（如果未设置）
    if not config.chart_to_json_llm.base_url:
        os.environ["CHART_TO_JSON_LLM_BASE_URL"] = base_url
    if not config.chart_to_json_llm.api_key:
        os.environ["CHART_TO_JSON_LLM_API_KEY"] = api_key
    if not config.chart_to_json_llm.model_name:
        os.environ["CHART_TO_JSON_LLM_MODEL_NAME"] = model_name
    
    # 重新加载配置
    config = load_config()
    
    # 获取 LLM 服务
    llm_service = get_llm_service()
    llm_service.set_config(config)
    
    # 获取模型
    model = llm_service.get_chart_to_json_chat_model()
    
    # 准备图像数据
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    
    mime_type = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    
    # 构建 LangChain 消息格式
    messages = [
        SystemMessage(content="你是一个专业的图表分析助手。请分析这张图片中的图表，并将其转换为结构化的JSON格式。"),
        HumanMessage(content=[
            {
                "type": "text",
                "text": "请分析这张图片，判断它是否为图表，并提供详细的分析结果。请以JSON格式输出。"
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_data}"
                }
            }
        ])
    ]
    
    print(f"Base URL: {config.chart_to_json_llm.base_url}")
    print(f"Model: {config.chart_to_json_llm.model_name}")
    print(f"Model type: {type(model).__name__}")
    print(f"Max tokens: {config.chart_to_json_llm.max_tokens} (from config, can be set via CHART_TO_JSON_LLM_MAX_TOKENS env var)")
    
    try:
        response = model.invoke(messages)
        
        print("\n✅ 调用成功!")
        print(f"Response type: {type(response)}")
        if hasattr(response, 'content'):
            print(f"Response content: {response.content[:200]}...")
        else:
            print(f"Response: {str(response)[:200]}...")
        return True, response
    except Exception as e:
        print(f"\n❌ 调用失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def main():
    """主函数"""
    print("GLM-4.6V API 调用验证脚本（仅测试 LLMService 方法）")
    print("="*80)
    
    # 从环境变量或配置获取参数
    base_url = os.getenv("CHART_TO_JSON_LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
    api_key = os.getenv("CHART_TO_JSON_LLM_API_KEY", "")
    model_name = os.getenv("CHART_TO_JSON_LLM_MODEL_NAME", "glm-4.6v")
    
    # 检查必需参数
    if not api_key:
        print("❌ 错误: 请设置 CHART_TO_JSON_LLM_API_KEY 环境变量")
        return
    
    # 确保 base_url 格式正确
    if not base_url.endswith("/"):
        base_url = base_url + "/"
    
    # 使用指定的测试图片路径
    default_image_path = os.path.join(
        project_root,
        "data",
        "processed",
        "mineru",
        "bee41df3-1778-44ad-bbec-5e5639157c7d_78",
        "0b11416d-3f52-454a-abdc-b1fe38e82715_bee41df3-1778-44ad-bbec-5e5639157c7d.pdf_extracted",
        "images",
        "46b4b7a0e9723a7fbf6fa993670899a0d695fc8b485d197116d6f8addc6cbead.jpg"
    )
    
    # 如果提供了命令行参数，使用参数中的路径；否则使用默认路径
    if len(sys.argv) > 1:
        test_image_path = sys.argv[1]
    else:
        test_image_path = default_image_path
    
    # 检查图片文件是否存在
    if not os.path.exists(test_image_path):
        print(f"❌ 错误: 图片文件不存在: {test_image_path}")
        print("\n请检查路径是否正确，或提供图片路径作为命令行参数：")
        print("用法: python test_glm_4_6v_api.py <image_path>")
        return
    
    print(f"\n使用测试图片: {test_image_path}")
    print(f"Base URL: {base_url}")
    print(f"Model: {model_name}")
    print(f"API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    
    # 只运行方法4: 使用 LLMService（完整流程）
    results = {}
    results["llm_service"] = test_llm_service_chart_to_json(base_url, api_key, model_name, test_image_path)
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    for method, (success, result) in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{method:30s} {status}")
        if not success:
            print(f"  错误: {result[:200]}...")
    
    # 显示测试结果
    if results["llm_service"][0]:
        print("\n✅ LLMService 方法测试成功")
    else:
        print("\n❌ LLMService 方法测试失败，请检查配置和网络连接")


if __name__ == "__main__":
    main()

