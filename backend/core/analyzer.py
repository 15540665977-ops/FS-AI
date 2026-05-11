"""
分析编排器
协调图像提取、RAG 检索、Claude Vision 调用，流式返回分析结果
"""
import asyncio
import base64
import os
from pathlib import Path
from typing import AsyncGenerator, List, Optional
import anthropic

from core.prompts import PromptTemplates
from core.rag import VectorRetriever
from core.web_search import WebSearchClient


_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

SYSTEM_PROMPT = """你是理想汽车非金属材料团队的谱图分析专家，专注于塑料和弹性体材料的 FTIR、DSC、TGA 分析。

分析规范（必须严格遵守）：
1. 每个峰位必须标注具体波数（cm⁻¹）或温度（°C）
2. 每条推断必须标注置信度：确认 / 疑似 / 不确定
3. 区分材料鉴定结论与失效推断结论，不得混用
4. 引用所依据的知识来源（本地知识库 / 标准谱图 / 联网文献）
5. 最后给出推荐后续验证测试

禁止使用模糊表述，如"可能"、"大约"、"类似"——用置信度标注代替。"""


class AnalysisOrchestrator:
    """分析编排主逻辑：图像编码 → RAG 检索 → Claude Vision 流式分析"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._async_client: Optional[anthropic.AsyncAnthropic] = None
        self.retriever = VectorRetriever()
        self.web_search = WebSearchClient()

    @property
    def async_client(self) -> anthropic.AsyncAnthropic:
        if self._async_client is None:
            self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._async_client

    # ------------------------------------------------------------------
    # 图像处理
    # ------------------------------------------------------------------

    def _encode_image(self, image_path: str) -> tuple[str, str]:
        """读取图像文件，返回 (base64字符串, media_type)"""
        ext = Path(image_path).suffix.lower()
        media_type = _MEDIA_TYPES.get(ext, "image/png")
        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        return data, media_type

    def _build_vision_messages(
        self, image_paths: List[str], prompt_text: str
    ) -> List[dict]:
        """构建 Claude Vision API 消息列表（多图支持）"""
        content = []
        for path in image_paths:
            data, media_type = self._encode_image(path)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            })
        content.append({"type": "text", "text": prompt_text})
        return [{"role": "user", "content": content}]

    # ------------------------------------------------------------------
    # 上下文构建
    # ------------------------------------------------------------------

    def _rag_context_sync(self, material_hint: str) -> str:
        """同步 RAG 检索（由 asyncio.to_thread 调用）"""
        try:
            material_results = self.retriever.search(material_hint, top_k=2)
            failure_results = self.retriever.search_failure_modes(material_hint, top_k=2)
            parts = []
            if material_results:
                parts.append("【材料知识库】")
                for r in material_results:
                    parts.append(f"- {r['snippet']}")
            if failure_results:
                parts.append("【失效模式库】")
                for r in failure_results:
                    parts.append(f"- {r['snippet']}")
            return "\n".join(parts)
        except Exception:
            return ""

    def _web_context_sync(self, material_hint: str) -> str:
        """同步 Tavily 搜索（由 asyncio.to_thread 调用）"""
        try:
            results = self.web_search.extract_technical_info(material_hint, "ftir_peaks")
            if not results:
                return ""
            parts = ["【联网文献】"]
            for r in results[:2]:
                parts.append(f"- {r['title']}: {r['snippet'][:200]}")
            return "\n".join(parts)
        except Exception:
            return ""

    async def _build_contexts(
        self, material_hint: Optional[str]
    ) -> tuple[str, str]:
        """并发获取 RAG + Web 上下文，均在线程池执行，不阻塞事件循环"""
        if not material_hint:
            return "", ""
        rag_ctx, web_ctx = await asyncio.gather(
            asyncio.to_thread(self._rag_context_sync, material_hint),
            asyncio.to_thread(self._web_context_sync, material_hint),
        )
        return rag_ctx, web_ctx

    def _build_prompt_text(
        self,
        analysis_type: str,
        material_hint: Optional[str],
        failure_background: Optional[str],
        rag_context: str,
        web_context: str,
    ) -> str:
        """组装发给 Claude 的用户文字部分"""
        parts = []
        if material_hint:
            parts.append(f"材料信息：{material_hint}")
        if failure_background:
            parts.append(f"失效背景：{failure_background}")
        if rag_context:
            parts.append(f"知识库参考：\n{rag_context}")
        if web_context:
            parts.append(f"联网文献补充：\n{web_context}")

        if analysis_type == "failure":
            parts.append("请对上传的谱图进行失效分析，对比失效件与好件差异，识别失效模式并给出推断依据及置信度。")
        elif analysis_type == "consistency":
            parts.append("请对比以上谱图，进行一致性检验，输出结构化差异表（标准值/实测值/偏差说明）和综合一致性判断（高/中/低）。")
        else:
            parts.append("请分析上传的谱图，识别材料类型、列出特征峰位（含归属和强度），评估热性能参数，指出异常迹象。")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # 流式分析
    # ------------------------------------------------------------------

    async def analyze_stream(
        self,
        images: List[str],
        analysis_type: str = "general",
        material_hint: Optional[str] = None,
        failure_background: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        核心分析方法：接收图像路径列表，流式 yield Claude 分析文本。

        Args:
            images: 磁盘上的图像路径列表
            analysis_type: "general" | "failure" | "consistency"
            material_hint: 用户提供的材料信息提示
            failure_background: 失效背景描述
        """
        rag_context, web_context = await self._build_contexts(material_hint)
        prompt_text = self._build_prompt_text(
            analysis_type, material_hint, failure_background, rag_context, web_context
        )
        messages = self._build_vision_messages(images, prompt_text)

        async with self.async_client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
