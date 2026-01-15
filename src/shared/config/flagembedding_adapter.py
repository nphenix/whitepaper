"""
FlagEmbedding 模型适配器
支持 Embedding 和 Rerank 模型

生成命令: 手动创建
生成时间: 2026-01-07
"""
import os
from typing import Any

from FlagEmbedding import FlagModel, FlagReranker

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


# 默认模型路径
DEFAULT_EMBEDDING_MODEL = "./models/bge-m3"
DEFAULT_RERANK_MODEL = "./models/bge-reranker-v2-m3"


class FlagEmbeddingModels:
    """FlagEmbedding 模型管理器 - 单例模式"""
    
    _embedding_model: FlagModel | None = None
    _rerank_model: FlagReranker | None = None
    
    @classmethod
    def get_embedding_model(
        cls,
        model_path: str | None = None,
        use_fp16: bool = True,
        device: str = "auto"
    ) -> FlagModel:
        """获取 Embedding 模型
        
        Args:
            model_path: 模型本地路径，默认使用 ./models/bge-m3
            use_fp16: 是否使用 FP16 加速
            device: 设备选择 "auto", "cuda", "cpu"
        """
        if cls._embedding_model is None:
            path = model_path or DEFAULT_EMBEDDING_MODEL
            if not os.path.exists(path):
                raise FileNotFoundError(f"Embedding 模型未找到: {path}")
            cls._embedding_model = FlagModel(
                path,
                use_fp16=use_fp16,
                device=device
            )
            # Windows 控制台常用 GBK 编码，直接 print emoji 会触发 UnicodeEncodeError
            logger.info("Embedding 模型加载成功: %s", path)
        return cls._embedding_model
    
    @classmethod
    def get_rerank_model(
        cls,
        model_path: str | None = None,
        use_fp16: bool = True,
        device: str = "auto",
    ) -> FlagReranker:
        """获取 Rerank 模型

        Args:
            model_path: 模型本地路径，默认使用 ./models/bge-reranker-v2-m3
            use_fp16: 是否使用 FP16 加速
            device: 设备选择 "auto", "cuda", "cpu"
        """
        if cls._rerank_model is None:
            path = model_path or DEFAULT_RERANK_MODEL
            if not os.path.exists(path):
                raise FileNotFoundError(f"Rerank 模型未找到: {path}")

            # 在 CPU 环境下强制关闭 fp16（避免底层框架/驱动导致的 meta tensor / dtype 问题）
            # 同时尽量显式指定 device，避免 auto 路径误判。
            try:
                import torch

                if device == "auto":
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                if device == "cpu":
                    use_fp16 = False
            except Exception:
                # torch 不可用时保持原参数
                pass

            # FlagEmbedding 的不同版本 FlagReranker 构造器签名可能不同；
            # 这里做兼容：优先尝试传入 device，失败则回退到旧签名。
            try:
                cls._rerank_model = FlagReranker(
                    path,
                    use_fp16=use_fp16,
                    device=device,
                )
            except TypeError:
                cls._rerank_model = FlagReranker(
                    path,
                    use_fp16=use_fp16,
                )
            # 同上：避免控制台编码问题
            logger.info(
                "Rerank 模型加载成功: %s (device=%s, use_fp16=%s)",
                path,
                device,
                use_fp16,
            )

            # 添加 rerank 方法到 FlagReranker 实例，使其兼容 hybrid_retriever 的调用
            def rerank_wrapper(
                query: str,
                documents: list[str],
                top_n: int | None = None
            ) -> list[dict[str, Any]]:
                """执行重排序（兼容接口）"""
                return cls.rerank(query, documents, top_n)

            cls._rerank_model.rerank = rerank_wrapper

        return cls._rerank_model
    
    @classmethod
    def embed(cls, texts: list[str]) -> list[list[float]]:
        """生成文本向量
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        model = cls.get_embedding_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()
    
    @classmethod
    def rerank(
        cls,
        query: str,
        documents: list[str],
        top_n: int | None = None
    ) -> list[dict[str, Any]]:
        """执行重排序
        
        Args:
            query: 查询文本
            documents: 文档列表
            top_n: 返回前 N 个结果
            
        Returns:
            [{"document": str, "index": int, "relevance_score": float}, ...]
        """
        model = cls.get_rerank_model()
        
        # 计算分数 (归一化)
        scores = model.compute_score(
            [[query, doc] for doc in documents],
            normalize=True
        )
        
        # 按分数降序排序
        ranked = sorted(
            zip(range(len(documents)), documents, scores),
            key=lambda x: x[2],
            reverse=True
        )
        
        top_n = top_n or len(documents)
        results = []
        for idx, doc, score in ranked[:top_n]:
            results.append({
                "document": doc,
                "index": idx,
                "relevance_score": float(score)
            })
        
        return results
    
    @classmethod
    def reset(cls):
        """重置模型（用于测试或重新加载）"""
        cls._embedding_model = None
        cls._rerank_model = None
        print("FlagEmbedding 模型已重置")


def embed_documents(texts: list[str]) -> list[list[float]]:
    """便捷函数：生成文档向量"""
    return FlagEmbeddingModels.embed(texts)


def embed_query(text: str) -> list[float]:
    """便捷函数：生成查询向量"""
    model = FlagEmbeddingModels.get_embedding_model()
    embedding = model.encode([text])
    return embedding[0].tolist()


def rerank_documents(
    query: str,
    documents: list[str],
    top_n: int | None = None
) -> list[dict[str, Any]]:
    """便捷函数：重排序文档"""
    return FlagEmbeddingModels.rerank(query, documents, top_n)
