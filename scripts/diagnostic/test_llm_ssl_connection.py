#!/usr/bin/env python3
"""
LLM API SSL连接诊断脚本

用于诊断和定位LLM API调用时的SSL连接错误。
可以测试不同的LLM API端点，捕获详细的SSL错误信息。

使用方法:
    python scripts/diagnostic/test_llm_ssl_connection.py
    python scripts/diagnostic/test_llm_ssl_connection.py --api-url https://open.bigmodel.cn/api/paas/v4
    python scripts/diagnostic/test_llm_ssl_connection.py --all-providers
"""

import argparse
import os
import sys
import ssl
import socket
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import OpenAI
from langchain_openai import ChatOpenAI

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.shared.config.settings import load_config
from src.shared.config.llm_service import get_llm_service
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class SSLConnectionDiagnostic:
    """SSL连接诊断工具"""

    def __init__(self):
        self.results = []

    def test_ssl_handshake(self, hostname: str, port: int = 443) -> dict[str, Any]:
        """测试SSL握手
        
        Args:
            hostname: 主机名
            port: 端口号
            
        Returns:
            测试结果字典
        """
        result = {
            "hostname": hostname,
            "port": port,
            "success": False,
            "error": None,
            "cert_info": None,
            "ssl_version": None,
        }
        
        try:
            # 创建SSL上下文
            context = ssl.create_default_context()
            
            # 创建socket连接
            sock = socket.create_connection((hostname, port), timeout=10)
            
            try:
                # 包装为SSL socket
                ssl_sock = context.wrap_socket(sock, server_hostname=hostname)
                
                # 获取证书信息
                cert = ssl_sock.getpeercert()
                result["cert_info"] = {
                    "subject": dict(x[0] for x in cert.get("subject", [])),
                    "issuer": dict(x[0] for x in cert.get("issuer", [])),
                    "version": cert.get("version"),
                    "serialNumber": cert.get("serialNumber"),
                    "notBefore": cert.get("notBefore"),
                    "notAfter": cert.get("notAfter"),
                }
                
                # 获取SSL版本
                result["ssl_version"] = ssl_sock.version()
                result["success"] = True
                
                ssl_sock.close()
                
            except ssl.SSLError as e:
                result["error"] = f"SSL错误: {type(e).__name__}: {e}"
                result["ssl_error_code"] = e.errno if hasattr(e, "errno") else None
                result["ssl_error_lib"] = e.lib if hasattr(e, "lib") else None
                result["ssl_error_reason"] = e.reason if hasattr(e, "reason") else None
                
            except Exception as e:
                result["error"] = f"连接错误: {type(e).__name__}: {e}"
                
            finally:
                sock.close()
                
        except socket.timeout:
            result["error"] = "连接超时"
        except socket.gaierror as e:
            result["error"] = f"DNS解析失败: {e}"
        except Exception as e:
            result["error"] = f"未知错误: {type(e).__name__}: {e}"
            
        return result

    def test_http_connection(self, url: str, api_key: str | None = None) -> dict[str, Any]:
        """测试HTTP连接（包括SSL）
        
        Args:
            url: API URL
            api_key: API密钥（可选）
            
        Returns:
            测试结果字典
        """
        result = {
            "url": url,
            "success": False,
            "status_code": None,
            "error": None,
            "error_type": None,
            "ssl_error_details": None,
            "response_time": None,
        }
        
        try:
            # 解析URL
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # 创建HTTP客户端
            timeout = httpx.Timeout(30.0, connect=10.0)
            client = httpx.Client(timeout=timeout, verify=True)
            
            # 测试连接
            start_time = time.time()
            
            # 尝试简单的GET请求（测试连接）
            try:
                response = client.get(base_url, follow_redirects=True)
                result["status_code"] = response.status_code
                result["success"] = True
            except httpx.HTTPStatusError as e:
                # HTTP状态错误不算连接失败
                result["status_code"] = e.response.status_code
                result["success"] = True
                result["error"] = f"HTTP状态错误: {e.response.status_code}"
            except httpx.ConnectError as e:
                result["error"] = f"连接错误: {e}"
                result["error_type"] = "ConnectError"
                # 检查是否是SSL错误
                if "SSL" in str(e) or "ssl" in str(e).lower():
                    result["ssl_error_details"] = str(e)
            except httpx.ConnectTimeout as e:
                result["error"] = f"连接超时: {e}"
                result["error_type"] = "ConnectTimeout"
            except Exception as e:
                result["error"] = f"未知错误: {type(e).__name__}: {e}"
                result["error_type"] = type(e).__name__
                # 检查是否是SSL相关错误
                error_str = str(e).lower()
                if "ssl" in error_str or "tls" in error_str or "certificate" in error_str:
                    result["ssl_error_details"] = str(e)
            
            result["response_time"] = time.time() - start_time
            client.close()
            
        except Exception as e:
            result["error"] = f"测试失败: {type(e).__name__}: {e}"
            result["error_type"] = type(e).__name__
            
        return result

    def test_openai_client(self, base_url: str, api_key: str, model_name: str = "gpt-4") -> dict[str, Any]:
        """测试OpenAI客户端连接
        
        Args:
            base_url: API基础URL
            api_key: API密钥
            model_name: 模型名称
            
        Returns:
            测试结果字典
        """
        result = {
            "base_url": base_url,
            "model_name": model_name,
            "success": False,
            "error": None,
            "error_type": None,
            "ssl_error_details": None,
            "response_time": None,
        }
        
        try:
            # 创建OpenAI客户端
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=30.0,
            )
            
            # 尝试简单的API调用
            start_time = time.time()
            
            try:
                # 使用一个非常简单的请求测试连接
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5,
                )
                result["success"] = True
                result["response_time"] = time.time() - start_time
                
            except Exception as e:
                error_type = type(e).__name__
                result["error"] = str(e)
                result["error_type"] = error_type
                result["response_time"] = time.time() - start_time
                
                # 检查是否是SSL错误
                error_str = str(e).lower()
                if "ssl" in error_str or "tls" in error_str or "certificate" in error_str:
                    result["ssl_error_details"] = str(e)
                    
                # 检查是否是连接错误
                if "connection" in error_str or "connect" in error_str:
                    # 提取更详细的错误信息
                    if hasattr(e, "__cause__") and e.__cause__:
                        cause = e.__cause__
                        if "SSL" in str(cause) or "ssl" in str(cause).lower():
                            result["ssl_error_details"] = str(cause)
                            
        except Exception as e:
            result["error"] = f"客户端创建失败: {type(e).__name__}: {e}"
            result["error_type"] = type(e).__name__
            
        return result

    def test_langchain_model(self, base_url: str, api_key: str, model_name: str = "gpt-4") -> dict[str, Any]:
        """测试LangChain模型连接
        
        Args:
            base_url: API基础URL
            api_key: API密钥
            model_name: 模型名称
            
        Returns:
            测试结果字典
        """
        result = {
            "base_url": base_url,
            "model_name": model_name,
            "success": False,
            "error": None,
            "error_type": None,
            "ssl_error_details": None,
            "response_time": None,
        }
        
        try:
            # 创建LangChain模型
            model = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url,
                timeout=30.0,
                max_retries=0,
            )
            
            # 尝试简单的调用
            start_time = time.time()
            
            try:
                response = model.invoke("test")
                result["success"] = True
                result["response_time"] = time.time() - start_time
                
            except Exception as e:
                error_type = type(e).__name__
                result["error"] = str(e)
                result["error_type"] = error_type
                result["response_time"] = time.time() - start_time
                
                # 检查是否是SSL错误
                error_str = str(e).lower()
                if "ssl" in error_str or "tls" in error_str or "certificate" in error_str:
                    result["ssl_error_details"] = str(e)
                    
                # 检查错误链
                current_error = e
                error_chain = []
                while current_error:
                    error_chain.append(str(current_error))
                    if hasattr(current_error, "__cause__") and current_error.__cause__:
                        current_error = current_error.__cause__
                    else:
                        break
                        
                # 检查错误链中是否有SSL错误
                for err_msg in error_chain:
                    if "SSL" in err_msg or "ssl" in err_msg.lower() or "UNEXPECTED_EOF" in err_msg:
                        result["ssl_error_details"] = err_msg
                        break
                        
        except Exception as e:
            result["error"] = f"模型创建失败: {type(e).__name__}: {e}"
            result["error_type"] = type(e).__name__
            
        return result

    def test_openai_sdk_adapter(self, base_url: str, api_key: str, model_name: str = "gpt-4") -> dict[str, Any]:
        """测试OpenAI SDK适配器连接（新的解决方案）
        
        Args:
            base_url: API基础URL
            api_key: API密钥
            model_name: 模型名称
            
        Returns:
            测试结果字典
        """
        result = {
            "base_url": base_url,
            "model_name": model_name,
            "success": False,
            "error": None,
            "error_type": None,
            "ssl_error_details": None,
            "response_time": None,
        }
        
        try:
            # 导入OpenAI SDK适配器
            from src.shared.config.openai_sdk_adapter import OpenAISDKAdapter
            from langchain_core.messages import HumanMessage
            
            # 创建适配器
            adapter = OpenAISDKAdapter(
                model_name=model_name,
                temperature=0.7,
                max_tokens=100,
                api_key=api_key,
                base_url=base_url,
                timeout=30.0,
            )
            
            # 尝试简单的调用
            start_time = time.time()
            
            try:
                messages = [HumanMessage(content="test")]
                response = adapter.invoke(messages)
                result["success"] = True
                result["response_time"] = time.time() - start_time
                
            except Exception as e:
                error_type = type(e).__name__
                result["error"] = str(e)
                result["error_type"] = error_type
                result["response_time"] = time.time() - start_time
                
                # 检查是否是SSL错误
                error_str = str(e).lower()
                if "ssl" in error_str or "tls" in error_str or "certificate" in error_str:
                    result["ssl_error_details"] = str(e)
                    
                # 检查错误链
                current_error = e
                error_chain = []
                while current_error:
                    error_chain.append(str(current_error))
                    if hasattr(current_error, "__cause__") and current_error.__cause__:
                        current_error = current_error.__cause__
                    else:
                        break
                        
                # 检查错误链中是否有SSL错误
                for err_msg in error_chain:
                    if "SSL" in err_msg or "ssl" in err_msg.lower() or "UNEXPECTED_EOF" in err_msg:
                        result["ssl_error_details"] = err_msg
                        break
                        
        except ImportError as e:
            result["error"] = f"导入适配器失败: {e}"
            result["error_type"] = "ImportError"
        except Exception as e:
            result["error"] = f"适配器创建或调用失败: {type(e).__name__}: {e}"
            result["error_type"] = type(e).__name__
            
        return result

    def print_result(self, test_name: str, result: dict[str, Any]):
        """打印测试结果
        
        Args:
            test_name: 测试名称
            result: 测试结果
        """
        print(f"\n{'='*60}")
        print(f"测试: {test_name}")
        print(f"{'='*60}")
        
        if result.get("success"):
            print("✅ 测试成功")
            if "response_time" in result:
                print(f"响应时间: {result['response_time']:.2f}秒")
            if "cert_info" in result:
                print(f"SSL版本: {result.get('ssl_version', 'N/A')}")
                cert = result["cert_info"]
                if cert:
                    print(f"证书主题: {cert.get('subject', {}).get('commonName', 'N/A')}")
                    print(f"证书颁发者: {cert.get('issuer', {}).get('commonName', 'N/A')}")
        else:
            print("❌ 测试失败")
            print(f"错误类型: {result.get('error_type', 'Unknown')}")
            print(f"错误信息: {result.get('error', 'N/A')}")
            
            if result.get("ssl_error_details"):
                print(f"\n🔍 SSL错误详情:")
                print(f"   {result['ssl_error_details']}")
                
            if "ssl_error_code" in result:
                print(f"\nSSL错误代码: {result['ssl_error_code']}")
            if "ssl_error_lib" in result:
                print(f"SSL错误库: {result['ssl_error_lib']}")
            if "ssl_error_reason" in result:
                print(f"SSL错误原因: {result['ssl_error_reason']}")
        
        # 保存结果
        self.results.append({
            "test_name": test_name,
            "result": result,
        })

    def print_summary(self):
        """打印测试总结"""
        print(f"\n{'='*60}")
        print("测试总结")
        print(f"{'='*60}")
        
        total = len(self.results)
        success = sum(1 for r in self.results if r["result"].get("success"))
        failed = total - success
        
        print(f"总测试数: {total}")
        print(f"成功: {success} ✅")
        print(f"失败: {failed} ❌")
        
        if failed > 0:
            print(f"\n失败的测试:")
            for r in self.results:
                if not r["result"].get("success"):
                    print(f"  - {r['test_name']}: {r['result'].get('error', 'Unknown error')}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="LLM API SSL连接诊断工具")
    parser.add_argument(
        "--api-url",
        type=str,
        help="要测试的API URL（例如: https://open.bigmodel.cn/api/paas/v4）",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API密钥（如果不提供，将从环境变量读取）",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="gpt-4",
        help="模型名称（默认: gpt-4）",
    )
    parser.add_argument(
        "--all-providers",
        action="store_true",
        help="测试所有配置的LLM提供商",
    )
    parser.add_argument(
        "--skip-ssl-handshake",
        action="store_true",
        help="跳过SSL握手测试",
    )
    
    args = parser.parse_args()
    
    diagnostic = SSLConnectionDiagnostic()
    
    # 加载配置
    try:
        config = load_config()
        llm_service = get_llm_service()
        llm_service.set_config(config)
        print("✅ 配置加载成功")
    except Exception as e:
        print(f"⚠️  配置加载失败: {e}")
        print("将使用环境变量中的配置")
        config = None
    
    # 如果指定了API URL，测试指定的URL
    if args.api_url:
        api_key = args.api_key or os.getenv("LLM_API_KEY")
        if not api_key:
            print("❌ 错误: 未提供API密钥（通过--api-key参数或LLM_API_KEY环境变量）")
            return
        
        # 解析URL获取主机名
        parsed = urlparse(args.api_url)
        hostname = parsed.hostname
        
        if not args.skip_ssl_handshake:
            # 测试SSL握手
            print(f"\n测试SSL握手: {hostname}")
            ssl_result = diagnostic.test_ssl_handshake(hostname)
            diagnostic.print_result(f"SSL握手 - {hostname}", ssl_result)
        
        # 测试HTTP连接
        http_result = diagnostic.test_http_connection(args.api_url)
        diagnostic.print_result(f"HTTP连接 - {args.api_url}", http_result)
        
        # 测试OpenAI客户端
        openai_result = diagnostic.test_openai_client(
            args.api_url, api_key, args.model_name
        )
        diagnostic.print_result(f"OpenAI客户端 - {args.api_url}", openai_result)
        
        # 测试LangChain模型（这是实际使用的，但有问题）
        langchain_result = diagnostic.test_langchain_model(
            args.api_url, api_key, args.model_name
        )
        diagnostic.print_result(f"LangChain模型 - {args.api_url}", langchain_result)
        
        # 测试OpenAI SDK适配器（新的解决方案）
        adapter_result = diagnostic.test_openai_sdk_adapter(
            args.api_url, api_key, args.model_name
        )
        diagnostic.print_result(f"OpenAI SDK适配器 - {args.api_url}", adapter_result)
        
    elif args.all_providers or config:
        # 测试所有配置的提供商
        if config and config.llm_config:
            base_url = config.llm_config.get("base_url")
            api_key = config.llm_config.get("api_key")
            model_name = config.llm_config.get("model_name", "gpt-4")
            
            if base_url and api_key:
                parsed = urlparse(base_url)
                hostname = parsed.hostname
                
                if not args.skip_ssl_handshake:
                    # 测试SSL握手
                    ssl_result = diagnostic.test_ssl_handshake(hostname)
                    diagnostic.print_result(f"SSL握手 - {hostname}", ssl_result)
                
                # 测试HTTP连接
                http_result = diagnostic.test_http_connection(base_url)
                diagnostic.print_result(f"HTTP连接 - {base_url}", http_result)
                
                # 测试OpenAI客户端
                openai_result = diagnostic.test_openai_client(base_url, api_key, model_name)
                diagnostic.print_result(f"OpenAI客户端 - {base_url}", openai_result)
                
                # 测试LangChain模型（这是实际使用的，但有问题）
                langchain_result = diagnostic.test_langchain_model(base_url, api_key, model_name)
                diagnostic.print_result(f"LangChain模型 - {base_url}", langchain_result)
                
                # 测试OpenAI SDK适配器（新的解决方案）
                adapter_result = diagnostic.test_openai_sdk_adapter(base_url, api_key, model_name)
                diagnostic.print_result(f"OpenAI SDK适配器 - {base_url}", adapter_result)
            else:
                print("❌ 错误: 配置中缺少base_url或api_key")
        else:
            # 从环境变量读取
            base_url = os.getenv("LLM_BASE_URL")
            api_key = os.getenv("LLM_API_KEY")
            model_name = os.getenv("LLM_MODEL_NAME", "gpt-4")
            
            if base_url and api_key:
                parsed = urlparse(base_url)
                hostname = parsed.hostname
                
                if not args.skip_ssl_handshake:
                    # 测试SSL握手
                    ssl_result = diagnostic.test_ssl_handshake(hostname)
                    diagnostic.print_result(f"SSL握手 - {hostname}", ssl_result)
                
                # 测试HTTP连接
                http_result = diagnostic.test_http_connection(base_url)
                diagnostic.print_result(f"HTTP连接 - {base_url}", http_result)
                
                # 测试OpenAI客户端
                openai_result = diagnostic.test_openai_client(base_url, api_key, model_name)
                diagnostic.print_result(f"OpenAI客户端 - {base_url}", openai_result)
                
                # 测试LangChain模型（这是实际使用的，但有问题）
                langchain_result = diagnostic.test_langchain_model(base_url, api_key, model_name)
                diagnostic.print_result(f"LangChain模型 - {base_url}", langchain_result)
                
                # 测试OpenAI SDK适配器（新的解决方案）
                adapter_result = diagnostic.test_openai_sdk_adapter(base_url, api_key, model_name)
                diagnostic.print_result(f"OpenAI SDK适配器 - {base_url}", adapter_result)
            else:
                print("❌ 错误: 环境变量中缺少LLM_BASE_URL或LLM_API_KEY")
                print("\n请设置以下环境变量:")
                print("  - LLM_BASE_URL: API基础URL")
                print("  - LLM_API_KEY: API密钥")
                print("  - LLM_MODEL_NAME: 模型名称（可选）")
    else:
        parser.print_help()
        return
    
    # 打印总结
    diagnostic.print_summary()
    
    # 提供建议
    print(f"\n{'='*60}")
    print("诊断建议")
    print(f"{'='*60}")
    
    failed_tests = [r for r in diagnostic.results if not r["result"].get("success")]
    if failed_tests:
        print("\n检测到SSL连接问题，建议:")
        print("1. 检查网络连接是否稳定")
        print("2. 检查防火墙/代理设置是否干扰SSL连接")
        print("3. 检查API服务提供商的服务器状态")
        print("4. 尝试使用不同的API端点（如果支持）")
        print("5. 检查SSL证书是否有效")
        print("6. 考虑添加重试机制来处理临时网络故障")
    else:
        print("\n✅ 所有测试通过，SSL连接正常")


if __name__ == "__main__":
    main()

