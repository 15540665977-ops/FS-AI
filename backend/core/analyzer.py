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
import httpx

from core.prompts import PromptTemplates
from core.rag import VectorRetriever
from core.web_search import WebSearchClient
from core.spectrum_extractor import SpectrumExtractor


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

谱图曲线分析规范（必须遵守）：
6. 必须分析图像中可见的所有吸收特征，包括图中未标注的峰
7. 对每个显著峰描述：峰形（窄/宽/不对称/有肩峰）、相对强度
8. 若提示词中提供了【图像曲线自动提取数据】，用该数值数据验证并补充目视观察结果；\
自动提取峰位精度约±20~50 cm⁻¹，最终以图中已标注数值和目视读取为准
9. 对于宽峰或重叠峰，明确指出可能存在多个组分叠加

禁止使用模糊表述，如"可能"、"大约"、"类似"——用置信度标注代替。"""


class AnalysisOrchestrator:
    """分析编排主逻辑：图像编码 → RAG 检索 → Claude Vision 流式分析"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._async_client: Optional[anthropic.AsyncAnthropic] = None
        self.retriever = VectorRetriever()
        self.web_search = WebSearchClient()
        self.spectrum_extractor = SpectrumExtractor()

    @property
    def async_client(self) -> anthropic.AsyncAnthropic:
        if self._async_client is None:
            # 显式传入 http_client，绕过 SDK 内部对 httpx 的 proxies 初始化
            # 避免 Python 3.14 / httpx 版本兼容问题
            self._async_client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                http_client=httpx.AsyncClient(),
            )
        return self._async_client

    @async_client.setter
    def async_client(self, value):
        self._async_client = value

    @async_client.deleter
    def async_client(self):
        self._async_client = None

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
    # 谱图曲线预处理
    # ------------------------------------------------------------------

    def _extract_one(self, image_path: str, session_dir: str) -> dict:
        """在线程中对单张图运行曲线提取（同步，供 to_thread 调用）"""
        return self.spectrum_extractor.extract_and_annotate(image_path, session_dir)

    async def _preprocess_spectra(
        self, images: List[str], session_dir: str
    ) -> tuple[List[str], str]:
        """
        并发对每张图运行谱图曲线提取。

        Returns:
            annotated_paths : 成功生成的标注图路径列表（与原图一起送给 Claude）
            extraction_text : 格式化的数值摘要文本（插入提示词）
        """
        tasks = [
            asyncio.to_thread(self._extract_one, img, session_dir)
            for img in images
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        annotated_paths: List[str] = []
        text_parts: List[str] = []

        for i, res in enumerate(results):
            if isinstance(res, Exception):
                continue
            ann = res.get("annotated_path")
            if ann:
                annotated_paths.append(ann)
            summary = res.get("summary_text", "")
            if summary and "提取失败" not in summary:
                label = f"[图像 {i + 1}]" if len(images) > 1 else ""
                text_parts.append(f"{label}\n{summary}".strip())

        extraction_text = "\n\n".join(text_parts)
        return annotated_paths, extraction_text

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
        extraction_context: str = "",
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
        if extraction_context:
            parts.append(extraction_context)

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
        # 谱图曲线预处理与 RAG/Web 检索并发执行
        session_dir = str(Path(images[0]).parent) if images else ""
        (annotated_paths, extraction_context), (rag_context, web_context) = (
            await asyncio.gather(
                self._preprocess_spectra(images, session_dir),
                self._build_contexts(material_hint),
            )
        )

        prompt_text = self._build_prompt_text(
            analysis_type, material_hint, failure_background,
            rag_context, web_context, extraction_context,
        )
        # 原始图 + 标注图（如有）一起送给 Claude
        all_images = images + annotated_paths
        messages = self._build_vision_messages(all_images, prompt_text)

        async with self.async_client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=6000,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # ── 结构化峰位提取 ────────────────────────────────────────────────

    async def extract_peaks_structured(
        self,
        images: List[str],
        analysis_summary: str,
    ) -> dict:
        """
        二次非流式调用：基于已完成的分析文本，从图像提取 FTIR 峰位 JSON。
        任何错误均静默，返回 {"suggested_material": None, "observed_peaks": []}。
        """
        import json as _json
        import re

        prompt = (
            "以下是对上方谱图的分析摘要：\n"
            f"{analysis_summary[:2000]}\n\n"
            "请基于谱图图像和上方分析，以 JSON 格式输出可识别的 FTIR 峰位。\n"
            "只输出合法 JSON，不要任何其他文字：\n"
            '{\n'
            '  "suggested_material": "最可能的知识库材料ID（如 PP、PA6、EPDM），若不确定填 null",\n'
            '  "observed_peaks": [\n'
            '    {"wavenumber": 2920, "assignment": "CH₂ 反对称伸缩", "intensity": "很强"}\n'
            '  ]\n'
            '}'
        )
        _EMPTY = {"suggested_material": None, "observed_peaks": []}
        try:
            messages = self._build_vision_messages(images, prompt)
            response = await self.async_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                messages=messages,
            )
            text = response.content[0].text.strip()
            match = re.search(r'\{[\s\S]*\}', text)
            if not match:
                return _EMPTY
            data = _json.loads(match.group())
            if not isinstance(data.get("observed_peaks"), list):
                data["observed_peaks"] = []
            valid_peaks = []
            for p in data["observed_peaks"]:
                if isinstance(p.get("wavenumber"), (int, float)):
                    valid_peaks.append({
                        "wavenumber": int(p["wavenumber"]),
                        "assignment": str(p.get("assignment", "")),
                        "intensity":  str(p.get("intensity", "中")),
                    })
            data["observed_peaks"] = valid_peaks
            if "suggested_material" not in data:
                data["suggested_material"] = None
            return data
        except Exception:
            return _EMPTY
