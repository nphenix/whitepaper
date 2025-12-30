"""
基于LLM的图表转JSON转换器(支持GLM-4.6V流式调用)

使用GLM-4.6V的流式调用功能实现图表识别和数据提取.
支持多模态输入(图像+文本),用于图表识别和结构化数据提取.

本模块所有文本处理均使用UTF-8编码,确保正确处理中文和其他Unicode字符.

生成命令: /speckit.implement T031B
生成时间: 2025-12-16
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger
from src.shared.utils.retry import RetryConfig, RetryHandler

logger = get_logger(__name__)


class ChartData(BaseModel):
    """图表数据结构化输出模型

    模型字段设计适应LLM实际返回的数据格式,而不是强制LLM返回特定格式.
    """

    chart_type: str | None = Field(
        default=None,
        description="图表类型(如:bar_chart, line_chart, pie_chart, scatter_plot等).如果LLM未返回则为None",
    )
    title: str | None = Field(
        default=None, description="图表标题(如果LLM未返回则为None)"
    )
    x_axis_label: str | None = Field(default=None, description="X轴标签")
    y_axis_label: str | None = Field(default=None, description="Y轴标签")
    data_series: list[dict[str, Any]] | None = Field(
        default=None,
        description="数据系列列表,每个系列包含name和data(如果LLM未返回则为None)",
    )
    categories: list[str] | None = Field(
        default=None, description="分类标签(用于柱状图,饼图等)"
    )
    confidence_score: float | None = Field(
        default=None, description="识别置信度(0-1之间,如果LLM未返回,则为None)"
    )
    has_accurate_data: bool | None = Field(
        default=None, description="是否具有准确的坐标数据(如果LLM未返回,则为None)"
    )
    notes: str | None = Field(default=None, description="备注信息")


class ChartAnalysisResult(BaseModel):
    """图表分析结果

    模型字段设计适应LLM实际返回的数据格式,而不是强制LLM返回特定格式.
    """

    is_chart: bool = Field(description="是否为图表")
    chart_type: str | None = Field(default=None, description="图表类型")
    confidence_score: float | None = Field(
        default=None, description="识别置信度(如果LLM未返回,则为None)"
    )
    has_accurate_data: bool | None = Field(
        default=None, description="是否具有准确的坐标数据(如果LLM未返回,则为None)"
    )
    description: str | None = Field(default=None, description="图表描述")
    chart_data: Any | None = Field(
        default=None,
        description="结构化图表数据(可以是ChartData对象,字典或列表,适应LLM返回格式)",
    )


def extract_json_from_content(content: str) -> dict[str, Any]:
    """直接将LLM返回的内容按JSON解析

    假设LLM已经严格按照提示词返回合法JSON字符串,
    不再做复杂的"抠JSON"逻辑.

    Args:
        content: LLM响应内容(应为JSON字符串)

    Returns:
        解析后的JSON字典

    Raises:
        json.JSONDecodeError: 当内容不是合法JSON时
    """
    stripped = content.strip()
    return json.loads(stripped)


class LLMChartToJsonConverter:
    """
    基于LLM的图表转JSON转换器(支持GLM-4.6V流式调用)

    支持多模态输入(图像+文本),使用GLM-4.6V的流式调用功能.
    用于图表识别和数据提取,将文档中的图表转换为结构化JSON格式.

    必须从T009创建的llm_service获取模型实例.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        max_retries: int = 3,
        retry_delay: float = 3.0,
    ):
        """初始化LLM图表转JSON转换器

        Args:
            llm_service: LLM服务实例(从T009获取),如果为None则使用全局实例
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
        """
        self.llm_service = llm_service or get_llm_service()

        # 初始化重试处理器
        retry_config = RetryConfig(
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        self.retry_handler = RetryHandler(retry_config)

        # 获取图表转JSON模型(必须从llm_service获取)
        try:
            self.model = self.llm_service.get_chart_to_json_chat_model()
            logger.info("成功获取图表转JSON模型")
        except Exception as e:
            logger.error("获取图表转JSON模型失败: %s", e)
            msg = f"无法获取图表转JSON模型: {e}"
            raise ProcessingError(msg) from e

        # 获取配置
        try:
            config = self.llm_service._config
            if config and hasattr(config, "chart_to_json_llm"):
                self.config = config.chart_to_json_llm
                self.confidence_threshold = self.config.confidence_threshold
                self.supports_vision = self.config.supports_vision
                self.enable_streaming = self.config.enable_streaming
                self.enable_thinking = self.config.enable_thinking
                max_retries = self.config.max_retries
                retry_delay = self.config.retry_delay
                logger.info(
                    f"从配置获取: confidence_threshold={self.confidence_threshold}, supports_vision={self.supports_vision}"
                )
            else:
                self.config = None
                self.confidence_threshold = 0.7
                self.supports_vision = True
                self.enable_streaming = True
                self.enable_thinking = True
                max_retries = 3
                retry_delay = 1.0
                logger.warning("无法获取配置,使用默认值")
        except Exception as e:
            self.config = None
            self.confidence_threshold = 0.7
            self.supports_vision = True
            self.enable_streaming = True
            self.enable_thinking = True
            max_retries = 3
            retry_delay = 1.0
            logger.warning("获取配置失败: %s,使用默认值", e)

        # 初始化重试处理器
        retry_config = RetryConfig(
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        self.retry_handler = RetryHandler(retry_config)

        # 图片处理状态记录:避免重复上传和处理同一张图片
        # 键为图片绝对路径,值为处理结果字典
        # 结构:{image_path: {'processed': bool, 'result': Optional[Dict], 'timestamp': float}}
        self._image_processing_status: dict[str, dict[str, Any]] = {}

        logger.info("LLM图表转JSON转换器初始化完成")

    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图像文件编码为base64字符串

        Args:
            image_path: 图像文件路径

        Returns:
            base64编码的图像字符串

        Raises:
            ProcessingError: 当图像编码失败时
        """
        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
                logger.debug(
                    "成功编码图像: %s, 大小: %s 字符",
                    image_path,
                    len(encoded_image),
                )
                return encoded_image
        except Exception as e:
            logger.error("图像编码失败: %s, 错误: %s", image_path, e)
            msg = f"无法编码图像文件: {e}"
            raise ProcessingError(msg) from e

    def _get_image_mime_type(self, image_path: str) -> str:
        """获取图像文件的MIME类型

        Args:
            image_path: 图像文件路径

        Returns:
            MIME类型字符串
        """
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
        }
        return mime_types.get(ext, "image/jpeg")

    def _prepare_image_data(self, image_path: str) -> tuple[str, str]:
        """准备图像数据(编码和MIME类型)

        用于避免重复编码同一张图片.

        Args:
            image_path: 图像文件路径

        Returns:
            (base64编码的图像字符串, MIME类型) 元组

        Raises:
            ProcessingError: 当图像编码失败时
        """
        encoded_image = self._encode_image_to_base64(image_path)
        mime_type = self._get_image_mime_type(image_path)
        return encoded_image, mime_type

    def _get_chart_analysis_system_message(self) -> str:
        """获取图表分析的系统提示词

        Returns:
            系统提示词字符串
        """
        return """你是一个专业的图表分析助手.请分析这张图片中的图表,并将其转换为结构化的JSON格式.

**你的主要任务**:
1. 判断图像中是否包含图表,重点关注饼图 (pie_chart) 和柱状图 (bar_chart)
2. 如果图片中包含多个图表,请分别识别每个图表
3. 如果是饼图或柱状图,请提取每个图表中的所有数据并转换为JSON格式
4. 如果不是图表或不是饼图/柱状图,请明确说明

**输出要求**:
- 请直接返回有效的JSON格式
- 如果只有一个图表:使用单个chart_data数组
- 如果有多个图表:使用chart_data数组,每个元素代表一个图表的数据
- 对于饼图:每个扇区包含{'label': '扇区名称', 'value': 数值, 'unit': '单位(如%,GW等)'}
- 对于柱状图:每个柱子包含{'category': '类别名称', 'value': 数值, 'unit': '单位(如%,GW等)'}
- 如果是百分比,请保留%符号在value或unit字段中
- 如果不是图表或不是饼图/柱状图,请在JSON中明确标记

**建议的JSON结构(仅供参考,可以根据实际情况调整)**:

单个图表:
{
  'is_chart': true,
  'chart_type': 'pie_chart' | 'bar_chart',
  'description': '对图表的简短描述',
  'chart_count': 1,
  'chart_data': [
    {'label': '扇区名称', 'value': 数值, 'unit': '单位'}  // 饼图
    // 或
    {'category': '类别名称', 'value': 数值, 'unit': '单位'}  // 柱状图
  ]
}

多个图表:
{
  'is_chart': true,
  'chart_type': 'pie_chart' | 'bar_chart',
  'description': '包含多个图表的描述',
  'chart_count': 2,
  'chart_data': [
    // 第一个图表分隔标记
    {'_chart_separator': 'chart_1'},
    // 第一个图表的数据
    {'label': '扇区名称', 'value': 数值, 'unit': '%'},
    // 第二个图表分隔标记
    {'_chart_separator': 'chart_2'},
    // 第二个图表的数据
    {'label': '扇区名称', 'value': 数值, 'unit': '%'}
  ]
}

请确保返回的是有效的JSON格式,数据尽量准确完整.如果有多個图表,请明确标识."""

    def _invoke_model(
        self, messages: list[dict[str, Any]], response_model: type | None = None
    ) -> str:
        """实际调用模型(不带重试)

        执行实际的模型调用,返回字符串响应.

        Args:
            messages: 消息列表
            response_model: 响应模型(忽略,直接返回字符串)

        Returns:
            字符串响应内容

        Raises:
            Exception: 当调用失败时
        """
        # 转换消息格式
        langchain_messages = []
        for msg in messages:
            if msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                if isinstance(msg["content"], list):
                    # 多模态消息
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                else:
                    # 文本消息
                    langchain_messages.append(HumanMessage(content=msg["content"]))

        # 直接调用模型,返回字符串
        response = self.model.invoke(langchain_messages)
        return response.content if hasattr(response, "content") else str(response)

    def _call_glm4v_normal(
        self, messages: list[dict[str, Any]], response_model: type | None = None
    ) -> str:
        """调用GLM-4.6V模型(带重试机制)

        包装模型调用,提供重试逻辑和错误处理.

        Args:
            messages: 消息列表
            response_model: 响应模型(忽略,直接返回字符串)

        Returns:
            字符串响应内容

        Raises:
            ProcessingError: 当调用失败时
        """
        try:
            return self.retry_handler.execute_with_retry(
                lambda: self._invoke_model(messages, response_model),
                operation_name="GLM-4.6V调用",
            )
        except Exception as e:
            msg = f"GLM-4.6V调用失败: {e}"
            raise ProcessingError(msg) from e

    def _analyze_image(self, image_path: str) -> ChartAnalysisResult:
        """分析图像是否为图表

        Args:
            image_path: 图像文件路径

        Returns:
            图表分析结果
        """
        logger.info("开始分析图像: %s", image_path)

        if not self.supports_vision:
            logger.warning("模型不支持视觉输入,返回非图表结果")
            return ChartAnalysisResult(
                is_chart=False,
                chart_type=None,
                confidence_score=0.0,
                has_accurate_data=False,
                description="模型不支持视觉输入",
            )

        try:
            # 准备图像数据(编码和MIME类型)
            encoded_image, mime_type = self._prepare_image_data(image_path)

            # 构建消息
            messages = [
                {
                    "role": "system",
                    "content": self._get_chart_analysis_system_message(),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请分析这张图片,判断它是否为图表,并提供详细的分析结果.请以JSON格式输出.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded_image}"
                            },
                        },
                    ],
                },
            ]

            # 调用模型,获取字符串响应
            response_text = self._call_glm4v_normal(messages, ChartAnalysisResult)

            # 不再生成调试文件,避免产生临时文件

            # 首先尝试灵活解析JSON,失败时才使用严格解析
            json_data = None
            try:
                # 清理响应文本,移除可能的markdown代码块标记
                cleaned_text = response_text.strip()
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                cleaned_text = cleaned_text.strip()

                # 尝试解析整个响应为JSON
                json_data = json.loads(cleaned_text)
                logger.info("成功使用灵活解析方式解析LLM响应为JSON格式")

            except json.JSONDecodeError as e:
                logger.warning("灵活JSON解析失败,尝试使用严格解析方式: %s", e)
                try:
                    # 备选方案:使用原来的严格解析
                    json_data = extract_json_from_content(response_text)
                    logger.info("成功使用严格解析方式解析LLM响应")
                except json.JSONDecodeError as e2:
                    logger.error("严格JSON解析也失败: %s", e2)
                    # 如果两种方式都失败,构造基本的错误结果
                    return ChartAnalysisResult(
                        is_chart=False,
                        chart_type=None,
                        confidence_score=0.0,
                        has_accurate_data=False,
                        description=f"JSON解析失败: {e2!s}",
                    )

            # 正常解析为模型对象(允许字段缺失/类型转换)
            result = ChartAnalysisResult.model_validate(json_data, strict=False)

            logger.info("图像分析完成: %s, is_chart=%s", image_path, result.is_chart)
            return result

        except Exception as e:
            logger.error("图像分析失败: %s, 错误: %s", image_path, e)
            # 返回默认结果
            return ChartAnalysisResult(
                is_chart=False,
                chart_type=None,
                confidence_score=0.0,
                has_accurate_data=False,
                description=f"分析失败: {e!s}",
            )

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名,使其适合文件系统

        Args:
            filename: 原始文件名

        Returns:
            清理后的文件名
        """
        # 移除或替换不安全的字符(但保留中文字符)
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # 移除控制字符
        sanitized = re.sub(r"[\x00-\x1f\x7f]", "", sanitized)

        # 移除文件名开头和结尾的空格和点
        sanitized = sanitized.strip(" .")

        # 确保文件名不为空
        if not sanitized:
            sanitized = "unnamed_chart.json"

        # 限制长度(保留中文字符,按字节计算长度以适应文件系统限制)
        # 大多数文件系统对文件名长度限制为255字节
        max_bytes = 200  # 留一些余量给.json扩展名
        if len(sanitized.encode("utf-8")) > max_bytes:
            # 按字节截断,确保不截断中文字符
            truncated = sanitized.encode("utf-8")[:max_bytes]
            try:
                sanitized = truncated.decode("utf-8")
            except UnicodeDecodeError:
                # 如果截断导致无效的UTF-8,逐个字符减少直到有效
                for i in range(max_bytes, 0, -1):
                    try:
                        sanitized = truncated[:i].decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        continue

        # 确保以.json结尾
        if not sanitized.endswith(".json"):
            # 如果文件名太长,移除部分内容以添加.json
            if len(sanitized.encode("utf-8")) > max_bytes - 5:  # 5字节为'.json'
                truncated = sanitized.encode("utf-8")[: max_bytes - 5]
                try:
                    sanitized = truncated.decode("utf-8") + ".json"
                except UnicodeDecodeError:
                    for i in range(max_bytes - 5, 0, -1):
                        try:
                            sanitized = truncated[:i].decode("utf-8") + ".json"
                            break
                        except UnicodeDecodeError:
                            continue
            else:
                sanitized += ".json"

        return sanitized

    def _contains_chinese(self, text: str) -> bool:
        """检查文本是否包含中文字符

        Args:
            text: 要检查的文本

        Returns:
            是否包含中文字符
        """
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    def _extract_chart_name_from_content_list(
        self, content_list_path: str, image_filename: str
    ) -> str | None:
        """从clean_content_list.json中提取图表标题

        Args:
            content_list_path: clean_content_list.json文件路径
            image_filename: 图像文件名(不含扩展名)

        Returns:
            图表标题(中文),如果未找到返回None
        """
        try:
            # 尝试多种可能的content_list.json文件名
            content_list_file = Path(content_list_path)

            # 检查传入的路径是文件还是目录
            if content_list_file.exists():
                if content_list_file.is_file():
                    # 如果是文件,直接使用
                    pass
                elif content_list_file.is_dir():
                    # 如果是目录,在目录中查找clean_content_list.json
                    content_list_file = content_list_file / "clean_content_list.json"
                else:
                    # 其他情况,尝试作为文件处理
                    pass
            else:
                # 如果路径不存在,检查是否是目录路径
                if content_list_file.is_dir():
                    content_list_file = content_list_file / "clean_content_list.json"
                else:
                    # 如果是文件路径但不存在,尝试在其父目录中查找
                    content_list_file = (
                        content_list_file.parent / "clean_content_list.json"
                    )

            if not content_list_file.exists():
                logger.debug("未找到clean_content_list.json文件: %s", content_list_file)
                return None

            with content_list_file.open(encoding="utf-8") as f:
                content_list = json.load(f)

            # 构建图片路径用于匹配(支持images/前缀或直接文件名)
            image_path_patterns = [
                f"images/{image_filename}",
                image_filename,
                f"{image_filename}.jpg",
                f"images/{image_filename}.jpg",
            ]

            # 遍历content_list查找匹配的图片(查找所有包含img_path的条目)
            for item in content_list:
                # 查找包含img_path的条目
                img_path = item.get("img_path", "")
                if not img_path:
                    continue

                # 提取img_path中的文件名(去掉images/前缀和扩展名)
                path_filename = Path(img_path).stem

                # 检查是否匹配
                if path_filename == image_filename or img_path in image_path_patterns:
                    # 获取image_caption
                    image_caption = item.get("image_caption", [])
                    if image_caption and isinstance(image_caption, list):
                        # 优先使用以'图'开头的中文标题
                        for caption in image_caption:
                            if caption and isinstance(caption, str) and caption.strip():
                                if self._contains_chinese(
                                    caption
                                ) and caption.startswith("图"):
                                    logger.debug(
                                        "从clean_content_list.json中提取到图表标题: %s",
                                        caption,
                                    )
                                    return caption.strip()

                        # 如果没有以'图'开头的中文标题,查找任何中文标题
                        for caption in image_caption:
                            if (
                                caption
                                and isinstance(caption, str)
                                and caption.strip()
                                and self._contains_chinese(caption)
                            ):
                                    logger.debug(
                                        "从clean_content_list.json中提取到图表标题: %s",
                                        caption,
                                    )
                                    return caption.strip()

                        # 如果没有中文标题,使用第一个标题
                        caption = image_caption[0] if image_caption else None
                        if caption and isinstance(caption, str) and caption.strip():
                            logger.debug(
                                "从clean_content_list.json中提取到图表标题: %s",
                                caption,
                            )
                            return caption.strip()

            logger.debug(
                "在clean_content_list.json中未找到匹配的图表标题: %s",
                image_filename,
            )
            return None

        except Exception as e:
            logger.warning(
                "从clean_content_list.json提取图表标题失败: %s, 错误: %s",
                content_list_path,
                e,
            )
            return None

    def _get_image_key(self, image_path: str) -> str:
        """获取图片的唯一标识键(使用绝对路径)

        Args:
            image_path: 图像文件路径

        Returns:
            图片的绝对路径字符串
        """
        try:
            return str(Path(image_path).resolve())
        except Exception:
            return str(image_path)

    def get_processing_status(self, image_path: str | None = None) -> dict[str, Any]:
        """获取图片处理状态

        Args:
            image_path: 图像文件路径,如果为None则返回所有图片的处理状态

        Returns:
            处理状态字典
        """
        if image_path:
            image_key = self._get_image_key(image_path)
            return self._image_processing_status.get(image_key, {})
        else:
            return {
                "total_images": len(self._image_processing_status),
                "processed_count": sum(
                    1
                    for s in self._image_processing_status.values()
                    if s.get("processed", False)
                ),
                "statuses": self._image_processing_status.copy(),
            }

    def clear_processing_status(self) -> None:
        """清空所有图片处理状态记录

        用于重新处理所有图片或释放内存.
        """
        count = len(self._image_processing_status)
        self._image_processing_status.clear()
        logger.info("已清空图片处理状态记录,共 %s 条记录", count)

    def process_single_image(
        self, image_path: str, output_dir: str | None = None
    ) -> dict[str, Any] | None:
        """处理单个图像文件

        处理图片并记录状态,用于追踪哪些图片已经处理过.
        每次调用都会重新处理图片,不会自动返回缓存结果.
        可以通过get_processing_status()查看处理历史.

        Args:
            image_path: 图像文件路径
            output_dir: 输出目录(可选)

        Returns:
            处理结果字典,包含分析结果和JSON数据,如果处理失败返回None
        """
        # 获取图片唯一标识
        image_key = self._get_image_key(image_path)

        # 检查是否已经处理过(仅用于日志记录,不影响处理流程)
        if image_key in self._image_processing_status:
            status = self._image_processing_status[image_key]
            if status.get("processed", False):
                logger.info("图片之前已处理过,将重新处理: %s", image_path)

        logger.info("开始处理单个图像: %s", image_path)

        # 标记为正在处理
        self._image_processing_status[image_key] = {
            "processed": False,
            "result": None,
            "timestamp": time.time(),
        }

        try:
            # 第一步:分析图像是否为图表
            analysis_result = self._analyze_image(image_path)

            # 检查置信度(如果LLM返回了置信度)
            confidence = (
                analysis_result.confidence_score
                if analysis_result.confidence_score is not None
                else 1.0
            )
            if confidence < self.confidence_threshold:
                logger.info(
                    "图像置信度 %s 低于阈值 %s,"
                    "跳过处理: %s",
                    confidence,
                    self.confidence_threshold,
                    image_path,
                )
                result = None
                # 记录处理结果(置信度不足)
                self._image_processing_status[image_key] = {
                    "processed": True,
                    "result": result,
                    "timestamp": time.time(),
                    "reason": "置信度不足",
                }
                return result

            # 如果不是图表,返回None
            if not analysis_result.is_chart:
                logger.info("图像不是图表,跳过处理: %s", image_path)
                result = None
                # 记录处理结果(不是图表)
                self._image_processing_status[image_key] = {
                    "processed": True,
                    "result": result,
                    "timestamp": time.time(),
                    "reason": "不是图表",
                }
                return result

            # 判断是否为饼状图或柱状图
            chart_type = analysis_result.chart_type or "unknown"

            # 如果LLM没有显式给出chart_type,但描述中明确提到"饼图",按饼图处理
            if chart_type in (None, "", "unknown"):
                desc = (analysis_result.description or "").lower()
                if (
                    "饼图" in analysis_result.description
                    or "pie chart" in desc
                    or "饼  图" in analysis_result.description
                ):
                    chart_type = "pie_chart"

            if chart_type not in ["pie_chart", "bar_chart"]:
                logger.info(
                    "图表类型为 %s,不是饼状图或柱状图,跳过JSON生成: %s",
                    chart_type,
                    image_path,
                )
                result = {
                    "image_path": image_path,
                    "analysis": analysis_result.dict(),
                    "json_generated": False,
                    "reason": f"图表类型为 {chart_type},不是饼状图或柱状图",
                }
                # 记录处理结果(不是饼图或柱状图)
                self._image_processing_status[image_key] = {
                    "processed": True,
                    "result": result,
                    "timestamp": time.time(),
                }
                return result

            # 如果是图表但没有准确数据,返回分析结果但不生成JSON
            # 如果LLM未返回has_accurate_data,默认认为有准确数据(允许处理)
            has_accurate = (
                analysis_result.has_accurate_data
                if analysis_result.has_accurate_data is not None
                else True
            )
            if not has_accurate:
                logger.info("图表没有准确坐标数据,跳过JSON生成: %s", image_path)
                result = {
                    "image_path": image_path,
                    "analysis": analysis_result.dict(),
                    "json_generated": False,
                    "reason": "图表没有准确坐标数据",
                }
                # 记录处理结果(没有准确数据)
                self._image_processing_status[image_key] = {
                    "processed": True,
                    "result": result,
                    "timestamp": time.time(),
                }
                return result

            # 第二步:从分析结果中直接构造 ChartData(只调用一次 LLM)
            raw_chart_data = analysis_result.chart_data
            chart_data_obj: ChartData | None = None
            if isinstance(raw_chart_data, ChartData):
                chart_data_obj = raw_chart_data
            elif isinstance(raw_chart_data, dict):
                try:
                    chart_data_obj = ChartData.model_validate(
                        raw_chart_data, strict=False
                    )
                except Exception as e:
                    logger.warning("从分析结果chart_data字典构造ChartData失败: %s", e)
                    chart_data_obj = None
            elif isinstance(raw_chart_data, list):
                # 如果LLM返回的是扁平列表(category/percentage),包装成ChartData的data_series
                try:
                    data_series = []
                    chart_separators = []

                    for item in raw_chart_data:
                        if isinstance(item, dict):
                            # 检查是否是图表分隔符
                            if "_chart_separator" in item:
                                chart_separators.append(item["_chart_separator"])
                                continue  # 跳过分隔符,但保持数据连续性

                            label = item.get("label") or item.get("category")
                            value = item.get("value") or item.get("percentage")
                            unit = item.get("unit", "")

                            if label is not None and value is not None:
                                # 保留原始单位和数值格式
                                data_item = {"label": label, "value": value}
                                if unit:
                                    data_item["unit"] = unit
                                data_series.append(data_item)

                    if data_series:
                        notes = None
                        if chart_separators:
                            notes = f"包含 {len(chart_separators)} 个图表分隔符: {', '.join(chart_separators)}"

                        chart_data_obj = ChartData(
                            chart_type=chart_type,
                            title=None,
                            x_axis_label=None,
                            y_axis_label=None,
                            data_series=data_series,
                            categories=None,
                            confidence_score=analysis_result.confidence_score,
                            has_accurate_data=analysis_result.has_accurate_data,
                            notes=notes,
                        )
                except Exception as e:
                    logger.warning("从分析结果chart_data列表构造ChartData失败: %s", e)
                    chart_data_obj = None

            if not chart_data_obj:
                logger.warning(
                    "图表数据提取失败(分析结果中缺少可用的chart_data): %s",
                    image_path,
                )
                result = {
                    "image_path": image_path,
                    "analysis": analysis_result.dict(),
                    "json_generated": False,
                    "reason": "数据提取失败",
                }
                # 记录处理结果(数据提取失败)
                self._image_processing_status[image_key] = {
                    "processed": True,
                    "result": result,
                    "timestamp": time.time(),
                }
                return result

            # 确定JSON文件名 - 优先使用clean_content_list.json中的标题
            image_filename = Path(image_path).stem

            # 优先从clean_content_list.json中提取图表标题
            # clean_content_list.json固定存在于图像文件所在目录的父目录
            chart_name = None
            # 从image_path推断clean_content_list.json的位置(images目录的父目录)
            image_file_path = Path(image_path)
            if image_file_path.parent.name == "images":
                # 如果图像在images子目录下,clean_content_list.json在父目录
                content_list_dir = image_file_path.parent.parent
            else:
                # 否则clean_content_list.json在同目录
                content_list_dir = image_file_path.parent

            extracted_caption = self._extract_chart_name_from_content_list(
                str(content_list_dir), image_filename
            )
            if extracted_caption:
                # 不清理图表标题,直接使用原始标题以保留中文
                chart_name = extracted_caption.strip()
                logger.debug(
                    "使用从clean_content_list.json提取的图表标题: %s",
                    chart_name,
                )

            # 如果clean_content_list.json中没有找到,尝试从图像文件名中提取
            if not chart_name or not chart_name.strip() or chart_name == image_filename:
                # 尝试从图像文件名中提取有意义的名称(移除哈希值)
                meaningful_name = re.sub(r"^[a-f0-9]+[_-]*", "", image_filename)
                if meaningful_name and meaningful_name != image_filename:
                    chart_name = meaningful_name

            # 如果还是没有有意义的名称,使用原始图片文件名(去掉扩展名)
            if not chart_name or not chart_name.strip() or chart_name == image_filename:
                # 去掉图片扩展名,保留原始文件名
                image_name_without_ext = Path(image_filename).stem
                chart_name = image_name_without_ext

            json_filename = self._sanitize_filename(f"{chart_name}.json")

            logger.debug(
                "JSON文件命名: 原始图像=%s, 提取名称=%s, 最终文件名=%s",
                image_filename,
                chart_name,
                json_filename,
            )

            # 为最终落地的 JSON 组织内容:
            # - 保留 LLM 判定的 is_chart / chart_type / has_accurate_data / description
            # - chart_data 尽量使用 LLM 原始给出的结构(避免无意义丢字段)
            json_payload: dict[str, Any] = {
                "is_chart": analysis_result.is_chart,
                "chart_type": chart_type,
                "has_accurate_data": has_accurate,
                "description": analysis_result.description,
            }
            if isinstance(raw_chart_data, (dict, list)):
                # 优先保留 LLM 给出的原始 chart_data 结构
                json_payload["chart_data"] = raw_chart_data
            else:
                # 兜底:用内部构造的 ChartData 展开为 dict
                json_payload["chart_data"] = chart_data_obj.dict()

            # 构建返回结果(保留内部用的 ChartData 结构,方便后续代码 / 调试)
            result = {
                "image_path": image_path,
                "analysis": analysis_result.dict(),
                "chart_data": chart_data_obj.dict(),
                "json_filename": json_filename,
                "json_generated": True,
            }

            # 如果指定了输出目录,保存JSON文件(写入的是 json_payload,而不是 ChartData 本体)
            if output_dir:
                output_path = Path(output_dir) / json_filename
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(json_payload, f, ensure_ascii=False, indent=2)
                logger.info("JSON文件已保存: %s", output_path)
                result["json_path"] = str(output_path)

            logger.info("单个图像处理完成: %s", image_path)

            # 记录处理结果
            self._image_processing_status[image_key] = {
                "processed": True,
                "result": result,
                "timestamp": time.time(),
            }

            return result

        except Exception as e:
            logger.error("单个图像处理失败: %s, 错误: %s", image_path, e)

            # 记录处理失败
            error_result = None
            self._image_processing_status[image_key] = {
                "processed": True,
                "result": error_result,
                "timestamp": time.time(),
                "error": str(e),
            }

            return None

    def process_images_in_directory(
        self, images_dir: str, output_dir: str | None = None
    ) -> dict[str, Any]:
        """处理目录中的所有图像文件

        Args:
            images_dir: 图像目录路径
            output_dir: 输出目录(可选)

        Returns:
            处理结果统计字典
        """
        logger.info("开始处理目录中的图像: %s", images_dir)

        images_path = Path(images_dir)
        if not images_path.exists():
            logger.error("图像目录不存在: %s", images_dir)
            return {
                "error": f"目录不存在: {images_dir}",
                "processed": [],
                "statistics": {},
            }

        # 支持的图像扩展名
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

        # 查找所有图像文件(只匹配文件,不匹配目录)
        image_files = []
        for ext in image_extensions:
            # 使用glob查找文件,然后过滤确保是文件而不是目录
            for file_path in images_path.glob(f"*{ext}"):
                if file_path.is_file():
                    image_files.append(file_path)
            for file_path in images_path.glob(f"*{ext.upper()}"):
                if file_path.is_file():
                    image_files.append(file_path)

        # 去重(避免大小写扩展名重复)
        image_files = list(set(image_files))

        if not image_files:
            logger.info("目录中没有找到图像文件: %s", images_dir)
            return {
                "processed": [],
                "statistics": {
                    "total_images": 0,
                    "charts_found": 0,
                    "json_generated": 0,
                    "processing_errors": 0,
                },
            }

        logger.info("找到 %s 个图像文件", len(image_files))

        # 处理每个图像
        processed_results = []
        charts_found = 0
        json_generated = 0
        processing_errors = 0

        for image_file in image_files:
            try:
                image_key = self._get_image_key(str(image_file))

                # 在同一批量处理会话中,如果图片已处理过,跳过(避免重复上传)
                if image_key in self._image_processing_status:
                    status = self._image_processing_status[image_key]
                    if status.get("processed", False):
                        logger.info("图片在本批次中已处理过,跳过: %s", image_file)
                        # 使用之前的结果
                        cached_result = status.get("result")
                        if cached_result:
                            processed_results.append(cached_result)
                            if cached_result.get("json_generated", False):
                                json_generated += 1
                            if cached_result.get("analysis", {}).get("is_chart", False):
                                charts_found += 1
                        continue

                result = self.process_single_image(str(image_file), output_dir)

                if result:
                    processed_results.append(result)
                    if result.get("json_generated", False):
                        json_generated += 1
                    if result.get("analysis", {}).get("is_chart", False):
                        charts_found += 1
                else:
                    processing_errors += 1

            except Exception as e:
                logger.error("处理图像文件失败: %s, 错误: %s", image_file, e)
                processing_errors += 1

        # 构建统计信息
        statistics = {
            "total_images": len(image_files),
            "charts_found": charts_found,
            "json_generated": json_generated,
            "processing_errors": processing_errors,
        }

        result = {"processed": processed_results, "statistics": statistics}

        logger.info(
          "目录图像处理完成: 总计 %s 个,"
          "发现图表 %s 个,"
          "生成JSON %s 个,"
          "处理错误 %s 个",
          statistics["total_images"],
          statistics["charts_found"],
          statistics["json_generated"],
          statistics["processing_errors"],
        )

        return result

    def process_mineru_directory(
        self, mineru_output_dir: str, create_datajson_dir: bool = True
    ) -> dict[str, Any]:
        """处理MinerU输出目录中的所有图表

        Args:
            mineru_output_dir: MinerU输出目录路径
            create_datajson_dir: 是否创建datajson子目录

        Returns:
            处理结果统计字典
        """
        logger.info("开始处理MinerU输出目录: %s", mineru_output_dir)

        mineru_path = Path(mineru_output_dir)
        if not mineru_path.exists():
            logger.error("MinerU输出目录不存在: %s", mineru_output_dir)
            return {
                "error": f"目录不存在: {mineru_output_dir}",
                "processed": [],
                "statistics": {},
            }

        # 查找clean.md文件
        clean_md_file = mineru_path / "clean.md"
        if not clean_md_file.exists():
            logger.warning("未找到clean.md文件: %s", clean_md_file)
            clean_md_file = None

        # 查找images目录
        images_dir = mineru_path / "images"
        if not images_dir.exists():
            logger.info("未找到images目录: %s", images_dir)
            return {
                "processed": [],
                "statistics": {
                    "total_images": 0,
                    "charts_found": 0,
                    "json_generated": 0,
                    "processing_errors": 0,
                },
            }

        # 创建输出目录
        if create_datajson_dir:
            output_dir = mineru_path / "datajson"
            output_dir.mkdir(exist_ok=True)
            logger.info("创建输出目录: %s", output_dir)
        else:
            output_dir = None

        # 处理images目录中的所有图像
        result = self.process_images_in_directory(
            str(images_dir), str(output_dir) if output_dir else None
        )

        # 添加目录信息
        result["mineru_output_dir"] = mineru_output_dir
        result["clean_md_file"] = str(clean_md_file) if clean_md_file else None
        result["images_dir"] = str(images_dir)
        result["output_dir"] = str(output_dir) if output_dir else None

        logger.info("MinerU目录处理完成: %s", mineru_output_dir)
        return result

    def process_cleaned_documents_directory(
        self,
        cleaned_docs_base_dir: str = "data/cleaned/documents",
        create_datajson_dirs: bool = True,
    ) -> dict[str, Any]:
        """处理已清洗文档目录下的所有图表

        遍历data/cleaned/documents/目录下的所有文档,处理其中的图表并生成JSON文件.

        Args:
            cleaned_docs_base_dir: 已清洗文档的基础目录路径
            create_datajson_dirs: 是否创建datajson子目录

        Returns:
            处理结果统计字典
        """
        logger.info("开始处理已清洗文档目录: %s", cleaned_docs_base_dir)

        base_path = Path(cleaned_docs_base_dir)
        if not base_path.exists():
            logger.error("已清洗文档目录不存在: %s", cleaned_docs_base_dir)
            return {
                "error": f"目录不存在: {cleaned_docs_base_dir}",
                "processed_documents": [],
                "overall_statistics": {},
            }

        # 遍历所有文档目录
        all_results = []
        total_statistics = {
            "total_documents": 0,
            "total_images": 0,
            "total_charts_found": 0,
            "total_json_generated": 0,
            "total_processing_errors": 0,
        }

        # 查找所有包含_extracted的目录(MinerU输出目录)
        # 注意:只遍历一级子目录,避免递归遍历导致无限循环
        for doc_dir in base_path.iterdir():
            # 确保是目录且不是符号链接(避免循环引用)
            if doc_dir.is_dir() and not doc_dir.is_symlink():
                # 查找文档下的_extracted目录(只查找直接子目录,不递归)
                extracted_dirs = [
                    d
                    for d in doc_dir.iterdir()
                    if d.is_dir()
                    and not d.is_symlink()
                    and d.name.endswith("_extracted")
                ]

                for extracted_dir in extracted_dirs:
                    logger.info("处理文档目录: %s", extracted_dir)

                    # 处理每个MinerU输出目录
                    result = self.process_mineru_directory(
                        str(extracted_dir), create_datajson_dirs
                    )

                    if "error" in result:
                        logger.warning(
                            "处理文档目录失败: %s, 错误: %s",
                            extracted_dir,
                            result["error"],
                        )
                        total_statistics["total_processing_errors"] += 1
                    else:
                        all_results.append(
                            {
                                "document_dir": str(doc_dir),
                                "extracted_dir": str(extracted_dir),
                                "result": result,
                            }
                        )

                        # 累计统计信息
                        stats = result.get("statistics", {})
                        total_statistics["total_documents"] += 1
                        total_statistics["total_images"] += stats.get("total_images", 0)
                        total_statistics["total_charts_found"] += stats.get(
                            "charts_found", 0
                        )
                        total_statistics["total_json_generated"] += stats.get(
                            "json_generated", 0
                        )
                        total_statistics["total_processing_errors"] += stats.get(
                            "processing_errors", 0
                        )

        # 构建最终结果
        final_result = {
            "base_directory": cleaned_docs_base_dir,
            "processed_documents": all_results,
            "overall_statistics": total_statistics,
            "summary": {
                "documents_processed": len(all_results),
                "total_images_processed": total_statistics["total_images"],
                "total_charts_found": total_statistics["total_charts_found"],
                "total_json_files_generated": total_statistics["total_json_generated"],
                "total_errors": total_statistics["total_processing_errors"],
            },
        }

        logger.info(
          "已清洗文档目录处理完成: 处理文档 %s 个,"
          "处理图像 %s 个,"
          "发现图表 %s 个,"
          "生成JSON %s 个,"
          "错误 %s 个",
          final_result["summary"]["documents_processed"],
          final_result["summary"]["total_images_processed"],
          final_result["summary"]["total_charts_found"],
          final_result["summary"]["total_json_files_generated"],
          final_result["summary"]["total_errors"],
        )

        return final_result


class LLMChartToJsonError(ProcessingError):
    """LLM图表转JSON专用异常"""
