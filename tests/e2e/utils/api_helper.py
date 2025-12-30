"""
API辅助函数

用于验证后端数据，不用于操作（操作必须通过浏览器）。
"""

import requests
from typing import Optional, Dict, Any
from pathlib import Path


BACKEND_URL = "http://localhost:8000"

def compute_stable_filename(file_path: str) -> str:
    """按后端 /upload 的规则计算稳定文件名（内容 hash 前32位 + 原扩展名）"""
    import hashlib

    p = Path(file_path)
    content = p.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()
    return f"{file_hash[:32]}{p.suffix}"


def check_backend_health() -> bool:
    """检查后端服务是否可用"""
    # 端到端测试时，后端可能在进行大文档处理/LLM调用，短超时会导致误判为“不可用”
    last_error: str | None = None
    for attempt in range(3):
        try:
            response = requests.get(f"{BACKEND_URL}/health", timeout=15)
            if response.status_code == 200:
                return True
            last_error = f"HTTP {response.status_code}"
        except requests.exceptions.ConnectionError as e:
            last_error = f"ConnectionError: {e}"
        except requests.exceptions.Timeout as e:
            last_error = f"Timeout: {e}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"

    print(f"后端健康检查失败({BACKEND_URL}/health): {last_error}")
    print(f"请确保后端服务已启动在 {BACKEND_URL}")
    return False


def get_outline(outline_id: str) -> Optional[Dict[str, Any]]:
    """获取大纲信息（用于验证）"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/outlines/{outline_id}",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None


def get_draft(draft_id: str) -> Optional[Dict[str, Any]]:
    """获取草稿信息（用于验证）"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/drafts/{draft_id}",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None


def get_sources(outline_id: str) -> Optional[Dict[str, Any]]:
    """获取来源信息（用于验证）"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/sources/{outline_id}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("data")
    except:
        pass
    return None


def find_document_by_filename(filename: str, limit: int = 5) -> Optional[Dict[str, Any]]:
    """根据文件名查找文档（用于验证）
    
    Args:
        filename: 文件名
        limit: 返回数量限制
        
    Returns:
        最新匹配的文档信息，如果没有找到则返回None
    """
    try:
        # 使用文档列表接口，通过搜索关键词查找
        response = requests.get(
            f"{BACKEND_URL}/api/v1/documents",
            params={"search": filename, "limit": limit},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # 文档列表接口可能返回 {"documents": [...]} 或直接返回列表
            documents = data.get("documents", []) if isinstance(data, dict) else data
            if not documents:
                return None
            # 返回文件名完全匹配的第一个文档（应该是最新的）
            for doc in documents:
                if doc.get("filename") == filename:
                    return doc
            # 如果没有完全匹配，返回第一个（可能是部分匹配）
            return documents[0]
    except Exception as e:
        print(f"查找文档失败: {e}")
    return None


def get_document_status(document_id: str) -> Optional[str]:
    """获取文档处理状态
    
    Args:
        document_id: 文档ID
        
    Returns:
        文档状态（"pending", "parsing", "indexed", "failed"），如果获取失败则返回None
    """
    try:
        # 增加超时时间，避免在处理大文档时超时
        response = requests.get(
            f"{BACKEND_URL}/api/v1/documents/{document_id}",
            timeout=30  # 增加超时时间到30秒，避免在处理中时超时
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("status")
    except Exception as e:
        print(f"获取文档状态失败: {e}")
    return None


def wait_for_document_processing(
    filename: str,
    timeout: int = 600,
    poll_interval: int = 5
) -> bool:
    """等待文档处理完成（轮询检查状态）
    
    这是最佳实践的实现方式：上传文件后，轮询检查文档处理状态，
    直到状态为 "indexed"（完成）或 "failed"（失败），而不是简单地等待固定时间。
    
    注意：轮询间隔默认设置为5秒，避免过于频繁的请求影响后端处理性能。
    
    Args:
        filename: 文件名
        timeout: 超时时间（秒），默认10分钟
        poll_interval: 轮询间隔（秒），默认5秒（避免过于频繁影响后端处理）
        
    Returns:
        True表示处理完成（INDEXED），False表示超时或失败
    """
    import time
    
    start_time = time.time()
    consecutive_errors = 0
    max_consecutive_errors = 3
    
    print(f"开始等待文档处理完成: {filename} (轮询间隔: {poll_interval}秒)")
    
    while time.time() - start_time < timeout:
        try:
            # 查找文档
            document = find_document_by_filename(filename)
            if not document:
                # 文档可能还未创建，等待后重试
                print(f"文档尚未找到，等待 {poll_interval} 秒后重试...")
                time.sleep(poll_interval)
                continue
            
            document_id = document.get("id")
            if not document_id:
                time.sleep(poll_interval)
                continue
            
            # 获取文档状态
            status = get_document_status(document_id)
            if not status:
                time.sleep(poll_interval)
                continue
            
            # 重置连续错误计数
            consecutive_errors = 0
            
            elapsed = int(time.time() - start_time)
            print(f"文档状态: {status} (已等待 {elapsed} 秒)")
            
            # 检查状态
            if status.lower() == "indexed":
                print(f"文档处理完成: {filename} (耗时 {elapsed} 秒)")
                return True
            elif status.lower() == "failed":
                print(f"文档处理失败: {filename}")
                return False
            # 如果是 pending 或 parsing，继续等待
            
            time.sleep(poll_interval)
            
        except Exception as e:
            consecutive_errors += 1
            elapsed = int(time.time() - start_time)
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"连续 {consecutive_errors} 次请求失败，可能后端正在处理中，延长等待时间...")
                # 如果连续失败，增加等待时间，避免频繁重试
                time.sleep(poll_interval * 2)
                consecutive_errors = 0  # 重置计数
            else:
                print(f"获取文档状态失败 (已等待 {elapsed} 秒): {e}")
                time.sleep(poll_interval)
    
    print(f"等待文档处理超时: {filename} (超时时间: {timeout} 秒)")
    return False
