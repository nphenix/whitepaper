"""
聊天API路由模块

提供AI聊天问答相关接口:
- POST /api/chat: AI 聊天问答
- GET /api/chat-without-rag: 无RAG聊天（仅LLM）
- _get_knowledge_base_id_from_outline_id: 从outline_id获取知识库ID
- get_hybrid_retriever: 获取混合检索引擎实例

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

import uuid
import glob
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from src.interfaces.api.error_handlers import (
    create_error_response,
    create_error_response_from_exception,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    ChatRequest,
    create_success_response,
)
from src.shared.config.llm_service import LLMService
from src.shared.utils.logging import get_logger

from .core import get_llm_service

if TYPE_CHECKING:
    from src.infrastructure.indexing.hybrid_retriever import HybridRetriever

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(tags=["聊天问答"])


def _get_knowledge_base_ids_from_outline_id(outline_id: str) -> list[str] | None:
    """从 outline_id 获取关联的知识库ID列表（支持多个上传文件）

    通过查询outline_sources表，查找source_type='uploaded_file'的记录，
    获取所有 document_id，然后生成对应的 knowledge_base_id 列表。

    注意：
    - 只有上传的文件（uploaded_file）会创建知识库
    - 推荐文献（recommended）和自定义URL（custom_url）不会创建知识库
    - 允许一个 outline 绑定多个 uploaded_file；此时应使用 MultiKBHybridRetriever 融合检索结果

    Args:
        outline_id: 大纲ID

    Returns:
        知识库ID列表（每项格式：kb_doc_{document_id的hex前16位}），如果未找到则返回None
    """
    try:
        from .core import get_source_adapter

        source_adapter = get_source_adapter()

        # 从数据库获取上传文件的来源
        sources = source_adapter.list(
            filters={"outline_id": outline_id, "source_type": "uploaded_file"},
            order_by="created_at ASC"
        )

        if not sources:
            logger.debug(
                "未找到outline_id=%s关联的上传文件（知识库仅支持上传文件，不支持推荐文献或自定义URL）",
                outline_id
            )
            return None

        kb_ids: list[str] = []
        bad_sources: list[str] = []

        for src in sources:
            document_id_str = src.get("source_id")
            if not document_id_str:
                bad_sources.append(str(src.get("id", "unknown")))
                continue
            try:
                document_uuid = uuid.UUID(str(document_id_str))
                kb_ids.append(f"kb_doc_{document_uuid.hex[:16]}")
            except (ValueError, TypeError):
                bad_sources.append(str(src.get("id", "unknown")))
                continue

        # 去重但保持顺序（created_at ASC）
        seen: set[str] = set()
        kb_ids = [x for x in kb_ids if not (x in seen or seen.add(x))]

        if bad_sources:
            logger.warning(
                "outline_id=%s 存在无法解析为 knowledge_base_id 的 uploaded_file source 记录: %s",
                outline_id,
                bad_sources,
            )

        if not kb_ids:
            return None

        logger.debug(
            "从outline_id=%s获取到knowledge_base_ids=%s (共%d个上传文件)",
            outline_id,
            kb_ids,
            len(sources),
        )
        return kb_ids

    except Exception as e:
        logger.warning(
            "获取knowledge_base_id失败（outline_id=%s）: %s",
            outline_id,
            e,
            exc_info=True
        )
        return None


def _get_knowledge_base_id_from_outline_id(outline_id: str) -> str | None:
    """向后兼容：返回第一个 knowledge_base_id（历史行为）"""
    kb_ids = _get_knowledge_base_ids_from_outline_id(outline_id)
    if not kb_ids:
        return None
    return kb_ids[0]


def _find_existing_bm25_index(knowledge_base_id: str | None = None) -> str | None:
    """查找已存在的BM25索引文件

    尝试多种可能的文件名格式，兼容不同版本的索引生成逻辑：
    - ./data/bm25_index/kb_kb_*.json (旧版本格式)
    - ./data/bm25_index/kb_kb_doc_*.json (旧版本格式变体)
    - ./data/bm25_index/kb_{knowledge_base_id}.json (废弃格式：历史遗留，可能存在)
    - ./data/bm25_index/default.pkl (废弃默认：仅兜底，通常不应依赖)

    Args:
        knowledge_base_id: 知识库ID，用于构建索引文件名

    Returns:
        索引文件路径（不带.json后缀），如果未找到则返回None
    """
    bm25_dir = Path("./data/bm25_index")
    if not bm25_dir.exists():
        logger.debug("BM25索引目录不存在: %s", bm25_dir)
        return None

    # 收集所有可能的模式
    patterns: list[tuple[str, str]] = []

    if knowledge_base_id:
        # 从 knowledge_base_id 提取 hex 部分用于匹配
        # knowledge_base_id 格式可能是 kb_doc_xxx 或直接是 hex
        hex_part = knowledge_base_id.replace("kb_doc_", "").replace("kb_", "")
        patterns.extend([
            (f"./data/bm25_index/kb_kb_{hex_part}.pkl", "旧版本格式(kb_kb_*.pkl)"),
            (f"./data/bm25_index/kb_kb_doc_{hex_part}.pkl", "旧版本格式(kb_kb_doc_*.pkl)"),
            (f"./data/bm25_index/kb_{knowledge_base_id}.pkl", "当前版本格式(kb_*.pkl)"),
        ])

    # 总是检查默认路径和所有json文件
    patterns.extend([
        ("./data/bm25_index/default.pkl", "废弃默认(default.pkl)"),
    ])

    # ⚠️ 重要：只有在 knowledge_base_id 为空（全局兜底模式）时，才允许“使用 kb_kb_*.json”。
    # 否则会出现：指定了 kb_doc_xxx，但 BM25 却拿了另一个文档的索引（导致全篇来源偏向同一个文件）。
    if not knowledge_base_id:
        json_files = list(bm25_dir.glob("kb_kb_*.json"))
        if json_files:
            # 兜底策略改为：优先选择“documents 数最多”的索引（更可能覆盖多文档知识库），再用 mtime 破同。
            # 背景：按 mtime 取最新经常会命中“单文档索引”，导致召回来源长期只剩一个文件。
            import json as _json

            scored: list[tuple[int, float, Path]] = []
            for jf in json_files:
                doc_count = 0
                try:
                    data = _json.loads(jf.read_text(encoding="utf-8"))
                    docs = data.get("documents") or []
                    if isinstance(docs, list):
                        doc_count = len(docs)
                except Exception:
                    doc_count = 0
                try:
                    mtime = float(jf.stat().st_mtime)
                except Exception:
                    mtime = 0.0
                scored.append((doc_count, mtime, jf))

            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            best = scored[0][2]
            logger.debug(
                "发现 %d 个旧版本BM25索引文件(按documents数优先): best=%s, documents=%d",
                len(json_files),
                best.name,
                scored[0][0],
            )
            return str(best).replace(".json", ".pkl")

    # 按模式查找
    for pattern, description in patterns:
        path = Path(pattern.replace('.pkl', '.json'))
        if path.exists():
            logger.info("找到已存在的BM25索引(%s): %s", description, path)
            return str(path).replace('.json', '.pkl')

    logger.debug("未找到已存在的BM25索引")
    return None


def get_hybrid_retriever(knowledge_base_id: str | list[str] | None = None) -> "HybridRetriever":
    """获取混合检索引擎实例

    Args:
        knowledge_base_id: 知识库ID（可选）。如果提供，将使用对应的collection名称创建索引构建器。
                          如果不提供，使用默认的collection名称（向后兼容）。

    Returns:
        HybridRetriever: 混合检索引擎实例

    Raises:
        ImportError: 如果LlamaIndex未安装
        HybridRetrieverError: 如果初始化失败（如配置错误、索引构建器创建失败等）
        ValueError: 如果参数无效

    Note:
        - 如果提供了knowledge_base_id，将使用：
          - 向量索引collection: kb_{knowledge_base_id}_vector
          - BM25索引文件: 自动查找已存在的索引（兼容旧版本格式）
          - 元数据索引表: kb_{knowledge_base_id}_metadata
        - 如果不提供knowledge_base_id（向后兼容），使用默认配置
        - BM25索引查找顺序：
          1. 优先查找已存在的旧版本索引文件（kb_kb_*.json）
          2. 其次查找当前版本格式（kb_{knowledge_base_id}.pkl）
          3. 最后使用默认路径或创建新索引
        - 如果初始化失败，会抛出异常而不是返回None，确保问题能被及时发现
    """
    from src.infrastructure.indexing.bm25_index import BM25IndexBuilder
    from src.infrastructure.indexing.hybrid_retriever import HybridRetriever, HybridRetrieverError
    from src.infrastructure.indexing.metadata_index import MetadataIndexBuilder
    from src.infrastructure.indexing.vector_index import VectorIndexBuilder
    from src.infrastructure.storage.chroma.connection import get_chroma_connection_manager
    from src.infrastructure.storage.sqlite.connection import get_sqlite_connection_manager

    # 支持多知识库：列表形式时创建 MultiKBHybridRetriever
    if isinstance(knowledge_base_id, list):
        kb_ids = [str(x).strip() for x in knowledge_base_id if str(x).strip()]
        # 去重保持顺序
        seen: set[str] = set()
        kb_ids = [x for x in kb_ids if not (x in seen or seen.add(x))]

        if not kb_ids:
            return get_hybrid_retriever(None)
        if len(kb_ids) == 1:
            return get_hybrid_retriever(kb_ids[0])

        from src.infrastructure.indexing.multi_kb_retriever import MultiKBHybridRetriever

        retrievers = [get_hybrid_retriever(kb_id) for kb_id in kb_ids]
        return MultiKBHybridRetriever(retrievers=retrievers)

    # 根据knowledge_base_id创建索引构建器（单知识库）
    if knowledge_base_id:
        # 使用指定的knowledge_base_id创建索引构建器
        # 注意：knowledge_base_id 已经是 kb_doc_xxx 格式
        # 使用与knowledge_base_helper.py中完全一致的命名规则
        vector_collection_name = f"kb_{knowledge_base_id}_vector"
        bm25_index_path = f"./data/bm25_index/kb_{knowledge_base_id}.pkl"
        metadata_table_name = f"kb_{knowledge_base_id}_metadata"

        logger.info(
            "使用知识库ID创建索引构建器: kb_id=%s, vector_collection=%s, bm25_path=%s, metadata_table=%s",
            knowledge_base_id,
            vector_collection_name,
            bm25_index_path,
            metadata_table_name
        )

        # 确保BM25索引目录存在
        bm25_dir = Path(bm25_index_path).parent
        bm25_dir.mkdir(parents=True, exist_ok=True)

        # 首先尝试查找已存在的索引文件（兼容旧版本格式）
        existing_bm25_path = _find_existing_bm25_index(knowledge_base_id)
        if existing_bm25_path:
            bm25_index_path = existing_bm25_path
            logger.info("使用已存在的BM25索引: %s", bm25_index_path)
        else:
            logger.debug("未找到已存在的BM25索引，将使用新路径: %s", bm25_index_path)

        # 检查BM25索引文件是否存在
        bm25_json_path = bm25_index_path.replace('.pkl', '.json')
        bm25_pkl_exists = Path(bm25_index_path).exists()
        bm25_json_exists = Path(bm25_json_path).exists()
        logger.debug(
            "BM25索引文件检查: pkl_path=%s (存在=%s), json_path=%s (存在=%s)",
            bm25_index_path,
            bm25_pkl_exists,
            bm25_json_path,
            bm25_json_exists
        )

        try:
            vector_builder = VectorIndexBuilder(
                collection_name=vector_collection_name,
                connection_manager=get_chroma_connection_manager(),
            )
            bm25_builder = BM25IndexBuilder(index_path=bm25_index_path)
            # 初始化后检查BM25索引状态
            try:
                bm25_stats = bm25_builder.get_stats()
                logger.info(
                    "BM25索引构建器初始化完成: is_built=%s, documents_count=%d, index_path=%s",
                    bm25_stats.get("is_built", False),
                    bm25_stats.get("documents_count", 0),
                    bm25_stats.get("index_path", "unknown")
                )
            except Exception as e:
                logger.warning("获取BM25索引状态失败: %s", e)
            metadata_builder = MetadataIndexBuilder(
                table_name=metadata_table_name,
                connection_manager=get_sqlite_connection_manager(),
            )
        except Exception as e:
            error_msg = (
                f"无法创建索引构建器（knowledge_base_id={knowledge_base_id}）: {e}. "
                "请检查知识库是否已正确创建，以及索引配置是否正确。"
            )
            logger.error(error_msg, exc_info=True)
            raise HybridRetrieverError(error_msg) from e
    else:
        # 向后兼容：使用默认配置
        logger.warning(
            "未提供knowledge_base_id，使用默认配置创建索引构建器。"
            "如果知识库已重建，请确保outline_id关联了上传文件。"
        )
        try:
            # 优先：自动发现当前 Chroma 中所有 kb_*_vector 集合并使用 MultiKB 检索
            # 背景：本项目常见形态是“每个知识库只有一份 PDF”（kb_kb_xxx），单库检索天然只会返回一个来源文件。
            # 若 outline_sources 未维护，则允许默认走“跨所有已存在 KB”的兜底召回，以恢复多来源。
            try:
                cm = get_chroma_connection_manager()
                collections = cm.list_collections()
                names: list[str] = []
                for c in collections:
                    n = getattr(c, "name", None)
                    if isinstance(n, str) and n:
                        names.append(n)
                    else:
                        # 兼容不同版本 list_collections 返回结构
                        s = str(c)
                        if s:
                            names.append(s)
                kb_ids: list[str] = []
                for name in names:
                    if not isinstance(name, str):
                        continue
                    if name == "whitepaper_documents":
                        continue
                    if name.startswith("kb_") and name.endswith("_vector"):
                        kb_id = name[len("kb_") : -len("_vector")]
                        if kb_id:
                            kb_ids.append(kb_id)
                # 去重保持顺序
                seen: set[str] = set()
                kb_ids = [x for x in kb_ids if not (x in seen or seen.add(x))]
                if kb_ids:
                    # 只有一个也按单库走，多个则自动 MultiKB
                    logger.info("默认检索：自动发现可用知识库: kb_count=%d", len(kb_ids))
                    return get_hybrid_retriever(kb_ids if len(kb_ids) > 1 else kb_ids[0])
            except Exception:
                # 自动发现失败则回退到历史默认逻辑
                pass

            vector_builder = VectorIndexBuilder()
            # 首先尝试查找已存在的索引文件（兼容旧版本格式）
            default_bm25_path = _find_existing_bm25_index() or "./data/bm25_index/default.pkl"
            Path(default_bm25_path).parent.mkdir(parents=True, exist_ok=True)
            bm25_builder = BM25IndexBuilder(index_path=default_bm25_path)
            # 检查默认BM25索引状态
            try:
                bm25_stats = bm25_builder.get_stats()
                logger.info(
                    "默认BM25索引状态: is_built=%s, documents_count=%d, index_path=%s",
                    bm25_stats.get("is_built", False),
                    bm25_stats.get("documents_count", 0),
                    bm25_stats.get("index_path", "unknown")
                )
            except Exception as e:
                logger.debug("获取默认BM25索引状态失败: %s", e)
            metadata_builder = MetadataIndexBuilder()
        except Exception as e:
            error_msg = (
                f"无法创建默认索引构建器: {e}. "
                "请检查系统配置和依赖是否正确安装。"
            )
            logger.error(error_msg, exc_info=True)
            raise HybridRetrieverError(error_msg) from e

    try:
        retriever = HybridRetriever(
            vector_index_builder=vector_builder,
            bm25_index_builder=bm25_builder,
            metadata_index_builder=metadata_builder,
            llm_service=get_llm_service(),
        )
        logger.info("HybridRetriever 初始化成功: kb_id=%s", knowledge_base_id or "默认")
        return retriever
    except HybridRetrieverError:
        # HybridRetriever自己抛出的异常，直接向上抛出
        raise
    except Exception as e:
        error_msg = (
            f"HybridRetriever 初始化失败（knowledge_base_id={knowledge_base_id or '默认'}）: {e}. "
            "请检查索引构建器配置和依赖是否正确。"
        )
        logger.error(error_msg, exc_info=True)
        raise HybridRetrieverError(error_msg) from e


@router.post(
    "/chat",
    response_model=dict[str, Any],
    summary="AI 聊天问答",
    description="基于知识库的AI聊天问答接口(前端适配接口)",
)
async def chat(
    request: ChatRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """
    AI 聊天问答接口(前端适配)

    基于知识库的RAG问答,支持:
    - 使用HybridRetriever进行混合检索
    - 可选的上下文记忆(基于outlineId)
    - 错误处理（失败时抛出异常，不降级）
    - 使用ChatPromptTemplate管理提示词(符合LangChain 1.0最佳实践)

    Args:
        request: 聊天请求
        llm_service: LLM服务

    Returns:
        统一响应格式:{ success: bool, response: str, timestamp: str, sources?: [...] }
    """
    # 获取HybridRetriever
    # 如果请求中包含outlineId，尝试获取对应的knowledge_base_id
    knowledge_base_id: str | list[str] | None = None
    if request.outlineId:
        kb_ids = _get_knowledge_base_ids_from_outline_id(request.outlineId)
        if kb_ids:
            knowledge_base_id = kb_ids if len(kb_ids) > 1 else kb_ids[0]
            logger.info(
                "从outlineId=%s获取到knowledge_base_id=%s",
                request.outlineId,
                knowledge_base_id,
            )
        else:
            logger.warning("未找到outlineId=%s关联的知识库，将使用默认配置", request.outlineId)

    try:
        from src.infrastructure.indexing.hybrid_retriever import HybridRetrieverError
        hybrid_retriever = get_hybrid_retriever(knowledge_base_id=knowledge_base_id)
    except (ImportError, HybridRetrieverError, ValueError) as e:
        logger.error("无法创建HybridRetriever: %s", e, exc_info=True)
        return create_error_response(
            "检索服务初始化失败",
            f"无法创建混合检索引擎: {str(e)}。请检查知识库配置和依赖是否正确安装。"
        )

    # 如果请求流式响应,使用流式端点
    if request.stream:
        from src.interfaces.api.routes.frontend_adapter_stream import _chat_stream
        return await _chat_stream(request, llm_service, hybrid_retriever)

    # 非流式响应
    try:
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        # 获取LLM模型
        try:
            llm = llm_service.get_chat_model()
        except Exception as e:
            logger.error("获取LLM模型失败: %s", e, exc_info=True)
            return create_error_response(
                "LLM服务不可用",
                "无法获取语言模型,请检查配置"
            )

        # 使用ChatPromptTemplate管理提示词(符合LangChain 1.0最佳实践)
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的文档分析助手,擅长回答关于文档内容的问题.

请根据提供的上下文信息回答问题.如果上下文中没有相关信息,请诚实地说不知道,不要编造答案.

回答要求:
1. 基于提供的上下文信息回答
2. 回答要准确,专业,简洁
3. 如果上下文不足,明确说明
4. 使用中文回答"""),
            MessagesPlaceholder(variable_name="chat_history"),  # 对话历史占位符
            ("human", """上下文信息:
{context}

问题:{input}

请基于上述上下文信息回答问题."""),
        ])

        # 加载对话历史(如果启用)
        chat_history = []
        if request.enableContext and request.outlineId:
            try:
                from src.infrastructure.storage.chat_history import (
                    get_chat_history_manager,
                )
                history_manager = get_chat_history_manager()
                # 加载最近6条消息(3轮对话)
                chat_history = history_manager.load_history(
                    outline_id=request.outlineId,
                    max_messages=6,
                )
                logger.info(
                    "加载对话历史: outline_id=%s, messages_count=%d",
                    request.outlineId,
                    len(chat_history)
                )
            except Exception as e:
                logger.warning("加载对话历史失败: %s,将使用无上下文模式", e)
                chat_history = []

        # 使用RAG模式进行检索
        try:
            # 执行混合检索
            top_k = request.topK or 5
            logger.info("执行RAG检索: query=%s, top_k=%d", request.message[:50], top_k)

            # 检索相关文档
            retrieved_nodes = hybrid_retriever.retrieve(
                query_str=request.message,
                top_k=top_k,
            )

            # 构建上下文
            context_parts = []
            sources_list = []

            for i, node_with_score in enumerate(retrieved_nodes):
                node = node_with_score.node
                # 获取文档来源信息
                metadata = getattr(node, 'metadata', {}) or {}
                doc_name = metadata.get('document_name', '未知文档')
                source = {
                    "id": i + 1,
                    "document": doc_name,
                    "relevance_score": node_with_score.score,
                }
                # 如果有文件名，也包含在来源中
                if 'filename' in metadata:
                    source["filename"] = metadata['filename']

                # 优先使用text属性，如果不存在则使用content
                text_content = getattr(node, 'text', None) or getattr(node, 'content', '')
                if text_content:
                    context_parts.append(f"【文档{i + 1}】{doc_name}:\n{text_content}")
                    sources_list.append(source)

            context_str = "\n\n".join(context_parts)

            if not context_str:
                logger.warning("未检索到相关内容")
                return create_error_response(
                    "未找到相关信息",
                    "未能从知识库中找到与您问题相关的内容。请尝试调整问题或上传更多相关文档。"
                )

            # 调用LLM生成回答
            logger.info("调用LLM生成回答, 上下文长度: %d 字符", len(context_str))
            response = await llm.ainvoke(
                prompt_template.format_messages(
                    chat_history=chat_history,
                    context=context_str,
                    input=request.message,
                )
            )

            # 提取回答内容
            response_text = ""
            if hasattr(response, 'content'):
                response_text = response.content
            elif hasattr(response, 'text'):
                response_text = response.text
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            # 限制回答长度，避免前端渲染过慢（最多3000字符）
            if len(response_text) > 3000:
                logger.warning("回答过长(%d字符)，将被截断", len(response_text))
                response_text = response_text[:3000] + "...\n\n[回答被截断]"

            # 保存对话历史(如果启用)
            if request.enableContext and request.outlineId:
                try:
                    from src.infrastructure.storage.chat_history import (
                        get_chat_history_manager,
                    )
                    history_manager = get_chat_history_manager()
                    # 保存用户问题和AI回答
                    history_manager.save_message(
                        outline_id=request.outlineId,
                        role="human",
                        content=request.message,
                    )
                    history_manager.save_message(
                        outline_id=request.outlineId,
                        role="ai",
                        content=response_text,
                    )
                    logger.debug("保存对话历史: outline_id=%s", request.outlineId)
                except Exception as e:
                    logger.warning("保存对话历史失败: %s", e)

            logger.info("聊天响应生成成功: 响应长度=%d字符", len(response_text))

            return create_success_response(
                data={
                    "response": response_text,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "sources": sources_list,
                }
            )

        except HybridRetrieverError as e:
            logger.error("RAG检索失败: %s", e, exc_info=True)
            return create_error_response(
                "检索服务错误",
                f"知识库检索失败: {str(e)}。请检查知识库配置或稍后重试。"
            )
        except Exception as e:
            logger.exception("RAG处理异常: %s", e)
            return create_error_response(
                "处理失败",
                f"处理您的请求时发生错误: {str(e)}"
            )

    except Exception as e:
        logger.exception("聊天接口异常: %s", e)
        return create_error_response_from_exception(e)


@router.post(
    "/chat-without-rag",
    response_model=dict[str, Any],
    summary="无RAG聊天",
    description="不使用RAG，仅使用LLM进行聊天问答（用于测试或无知识库场景）",
)
async def _chat_without_rag(
    request: ChatRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """
    无RAG聊天接口（用于测试或无知识库场景）

    不使用RAG检索，仅使用LLM进行对话。

    Args:
        request: 聊天请求
        llm_service: LLM服务

    Returns:
        统一响应格式:{ success: bool, response: str, timestamp: str }
    """
    try:
        from datetime import datetime

        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        # 获取LLM模型
        try:
            llm = llm_service.get_chat_model()
        except Exception as e:
            logger.error("获取LLM模型失败: %s", e, exc_info=True)
            return create_error_response(
                "LLM服务不可用",
                "无法获取语言模型,请检查配置"
            )

        # 使用ChatPromptTemplate管理提示词
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "你是一个专业的AI助手。请用中文回答问题。"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        # 加载对话历史(如果启用)
        chat_history = []
        if request.enableContext and request.outlineId:
            try:
                from src.infrastructure.storage.chat_history import (
                    get_chat_history_manager,
                )
                history_manager = get_chat_history_manager()
                chat_history = history_manager.load_history(
                    outline_id=request.outlineId,
                    max_messages=6,
                )
            except Exception as e:
                logger.warning("加载对话历史失败: %s", e)
                chat_history = []

        # 调用LLM生成回答
        response = await llm.ainvoke(
            prompt_template.format_messages(
                chat_history=chat_history,
                input=request.message,
            )
        )

        # 提取回答内容
        response_text = ""
        if hasattr(response, 'content'):
            response_text = response.content
        elif hasattr(response, 'text'):
            response_text = response.text
        elif isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)

        # 保存对话历史(如果启用)
        if request.enableContext and request.outlineId:
            try:
                from src.infrastructure.storage.chat_history import (
                    get_chat_history_manager,
                )
                history_manager = get_chat_history_manager()
                history_manager.save_message(
                    outline_id=request.outlineId,
                    role="human",
                    content=request.message,
                )
                history_manager.save_message(
                    outline_id=request.outlineId,
                    role="ai",
                    content=response_text,
                )
            except Exception as e:
                logger.warning("保存对话历史失败: %s", e)

        return create_success_response(
            data={
                "response": response_text,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    except Exception as e:
        logger.exception("无RAG聊天异常: %s", e)
        return create_error_response_from_exception(e)


__all__ = ["router", "_get_knowledge_base_id_from_outline_id", "get_hybrid_retriever"]
