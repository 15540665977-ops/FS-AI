"""
谱图分析对话路由
接收上传文件，流式返回 AI 分析结果（SSE 格式）
"""
import asyncio
import io
import json
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.analyzer import AnalysisOrchestrator
from core.paths import UPLOADS_DIR
from core.security import CurrentUser, get_current_user
from core.file_parser import process_pdf_file
from db.database import get_db
from db.models import AnalysisCase, StandardSpectrum

router = APIRouter(dependencies=[Depends(get_current_user)])

UPLOAD_DIR = UPLOADS_DIR / "sessions"
MAX_UPLOAD_BYTES = int(__import__("os").environ.get("MAX_UPLOAD_BYTES", 20 * 1024 * 1024))
MAX_UPLOAD_FILES = int(__import__("os").environ.get("MAX_UPLOAD_FILES", 10))

_orchestrator: Optional[AnalysisOrchestrator] = None


def get_orchestrator() -> AnalysisOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AnalysisOrchestrator()
    return _orchestrator


async def _extract_images(files: List[UploadFile], session_dir: Path) -> List[str]:
    """
    将上传的 PDF/图片文件提取为图像路径列表。
    UploadFile.read() 是协程，必须 await，然后包装为 BytesIO 传给同步解析器。
    """
    session_dir.mkdir(parents=True, exist_ok=True)
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=413, detail=f"单次最多上传 {MAX_UPLOAD_FILES} 个文件")
    image_paths = []

    for file in files:
        filename = Path(file.filename or "upload").name
        ext = Path(filename).suffix.lower()
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"文件过大，单文件最大 {MAX_UPLOAD_BYTES // 1024 // 1024} MB")

        if ext == ".pdf":
            pdf_obj = io.BytesIO(content)
            stem = Path(filename).stem[:15].replace(" ", "_")
            paths = process_pdf_file(pdf_obj, session_dir, prefix=f"{stem}_")
            image_paths.extend(paths)
        elif ext in (".pptx", ".ppt"):
            raise HTTPException(
                status_code=415,
                detail=f"暂不支持 PPT 格式：{filename}，请先转为 PDF 或图片",
            )
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            save_path = session_dir / filename
            save_path.write_bytes(content)
            image_paths.append(str(save_path))
        else:
            raise HTTPException(
                status_code=415,
                detail=f"不支持的文件格式：{ext}",
            )

    return image_paths


async def _extract_images_per_file(
    files: List[UploadFile], session_dir: Path
) -> List[List[str]]:
    """
    每个上传文件独立提取为图像路径列表。
    返回 [[file0_imgs], [file1_imgs], ...]，供对比分析使用。
    """
    session_dir.mkdir(parents=True, exist_ok=True)
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=413, detail=f"单次最多上传 {MAX_UPLOAD_FILES} 个文件")
    groups: List[List[str]] = []
    for file in files:
        filename = Path(file.filename or "upload").name
        ext = Path(filename).suffix.lower()
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"文件过大，单文件最大 {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
        paths: List[str] = []
        if ext == ".pdf":
            stem = Path(filename).stem[:15].replace(" ", "_")
            paths = process_pdf_file(io.BytesIO(content), session_dir, prefix=f"{stem}_")
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            save_path = session_dir / filename
            save_path.write_bytes(content)
            paths = [str(save_path)]
        else:
            raise HTTPException(status_code=415, detail=f"不支持的文件格式：{ext}")
        if paths:
            groups.append(paths)
    return groups


def _load_reference_images(
    reference_source: Optional[str],
    reference_id: Optional[int],
    db: Session,
) -> List[str]:
    """从标准谱图库加载对照图像路径"""
    if reference_source != "library" or not reference_id:
        return []
    spectrum = db.query(StandardSpectrum).filter(StandardSpectrum.id == reference_id).first()
    if not spectrum:
        return []
    return [
        p for p in [spectrum.ir_image_path, spectrum.dsc_image_path, spectrum.tga_image_path]
        if p and Path(p).exists()
    ]


def _extract_material_from_text(text: str) -> Optional[str]:
    """
    从 AI 分析报告中提取材料名称。
    按优先级：推断亚型 → 句内均为+大写缩写 → 材料类型 → 鉴定结论
    使用非贪婪量词避免跳过材料名首字母。
    """
    import re
    _CN = "\u4e00-\u9fff"
    patterns = [
        # 1. "推断亚型：PA6" — 非贪婪，直接从冒号后起始捕获
        f"推断亚型[：:][^\\n]{{0,3}}?([A-Za-z0-9{_CN}]{{2,20}})",
        # 2. "材料鉴定结论：两条曲线基材均为 PEEK" — 寻找行内大写缩写
        r"材料(?:类型|鉴定结论|鉴定|名称)[：:][^\n]*均?为\s*([A-Z]{2,8}(?:[/-][A-Z0-9]{1,4})?)",
        # 3. "材料类型：聚酰胺" — 直接跟随（非贪婪上下文）
        f"材料(?:类型|鉴定|名称)[：:][^\\n]{{0,3}}?([{_CN}]{{2,15}})",
        # 4. "基材均为 PEEK" — 句内全大写缩写
        r"(?:基材|基体)均?为\s*([A-Z]{2,8}(?:[/-][A-Z0-9]{1,4})?)",
        # 5. "鉴定结论：..." — 兜底
        f"鉴定结论[：:][^\\n]{{0,3}}?([A-Za-z0-9{_CN}]{{2,20}})",
    ]
    for pat in patterns:
        m = re.search(pat, text[:8000], re.MULTILINE)  # 结论区通常在详细峰表之后
        if m:
            name = m.group(1)
            name = re.sub(r"[*_`#>]", "", name).replace(" ", "")
            name = re.sub(r"（[^）]{0,20}）", "", name)
            name = name.strip("：:(),，\t")
            if 2 <= len(name) <= 25:
                return name
    return None


def _extract_confidence_from_text(text: str) -> str:
    """
    从 AI 分析报告中提取综合置信度。
    优先从材料鉴定结论段落提取「置信度：确认/疑似/不确定」。
    """
    import re
    CONF_MAP = {"确认": "high", "疑似": "medium", "不确定": "low"}

    # 优先：在材料类型/综合结论段落附近找置信度
    priority = re.search(
        r"(?:材料类型|材料鉴定|综合结论|🔵)[^\n]{0,60}\n[^\n]{0,30}置信度[：:][^确疑不]{0,3}(确认|疑似|不确定)",
        text[:8000], re.DOTALL,
    )
    if priority:
        return CONF_MAP[priority.group(1)]

    # 备用：统计全文前8000字中各置信度出现次数，取最多的
    counts: dict = {}
    for m in re.finditer(r"置信度[：:][^确疑不]{0,3}(确认|疑似|不确定)", text[:8000]):
        k = m.group(1)
        counts[k] = counts.get(k, 0) + 1
    if counts:
        return CONF_MAP[max(counts, key=counts.get)]

    # 再兜底：统计【确认】【疑似】【不确定】格式
    bracket: dict = {}
    for m in re.finditer(r"【(确认|疑似|不确定)】", text[:8000]):
        k = m.group(1)
        bracket[k] = bracket.get(k, 0) + 1
    if bracket:
        return CONF_MAP[max(bracket, key=bracket.get)]
    return "unknown"


def _save_case(
    db: Session,
    image_paths: List[str],
    analysis_type: str,
    material_hint: Optional[str],
    reference_source: Optional[str],
    reference_id: Optional[int],
    full_text: str,
    created_by: Optional[str] = None,
) -> str:
    """分析完成后将结果保存为案例记录，返回案例编号"""
    from api.cases import _next_case_no

    # 材料名：优先用户填写 → 从报告文本提取 → 兜底"未知"
    material_name = (
        material_hint
        or _extract_material_from_text(full_text)
        or "未知"
    )

    # 结论摘要：取分析文本的最后一段（通常是综合结论）
    conclusion = ""
    if full_text:
        # 找最后一个二级标题之后的内容作为结论摘要
        import re
        parts = re.split(r'\n#{1,3} ', full_text)
        last_section = parts[-1].strip() if parts else full_text
        conclusion = last_section[:600]

    _TYPE_CN = {
        "general": "通用分析",
        "failure": "失效分析",
        "consistency": "一致性检验",
        "joint": "联合分析",
        "cross_compare": "跨材料对比",
    }

    case_no = _next_case_no(db)
    case = AnalysisCase(
        case_no=case_no,
        material_name=material_name,
        failure_description=_TYPE_CN.get(analysis_type, analysis_type),
        uploaded_files=json.dumps(
            [Path(p).name for p in image_paths],   # 只存文件名，不存绝对路径
            ensure_ascii=False,
        ),
        reference_source=reference_source,
        reference_id=reference_id,
        analysis_result=full_text,
        conclusion=conclusion,
        confidence_level=_extract_confidence_from_text(full_text),
        created_by=created_by,
    )
    db.add(case)
    db.commit()
    return case_no


@router.post("/stream")
async def analyze_stream(
    current_user: CurrentUser,
    files: List[UploadFile] = File(...),
    analysis_type: str = Form("general"),
    material_hint: Optional[str] = Form(None),
    failure_background: Optional[str] = Form(None),
    reference_source: Optional[str] = Form(None),
    reference_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    主分析接口：上传谱图文件，流式返回 AI 分析（SSE）。

    前端监听格式：
      data: {"content": "分析文本片段"}
      data: {"done": true, "case_no": "FA-2026-001"}
      data: {"error": "错误信息"}
    """
    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    orchestrator = get_orchestrator()

    try:
        image_paths = await _extract_images(files, session_dir)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败：{e}")

    if not image_paths:
        raise HTTPException(status_code=400, detail="未找到有效的谱图图像")

    ref_images = _load_reference_images(reference_source, reference_id, db)
    all_images = ref_images + image_paths

    async def event_stream():
        full_text = []
        try:
            async for chunk in orchestrator.analyze_stream(
                images=all_images,
                analysis_type=analysis_type,
                material_hint=material_hint,
                failure_background=failure_background,
            ):
                full_text.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

            case_no = _save_case(
                db, image_paths, analysis_type,
                material_hint, reference_source, reference_id,
                "".join(full_text), current_user.username,
            )

            # 结构化峰位提取 — 失败不影响 done 事件
            try:
                spectra = await orchestrator.extract_peaks_structured(
                    image_paths,
                    "".join(full_text),
                )
                image_urls = [
                    f"/uploads/sessions/{session_id}/{Path(p).name}"
                    for p in image_paths
                ]
                spectra_payload = {
                    "type": "spectra_data",
                    "suggested_material": spectra.get("suggested_material"),
                    "observed_peaks": spectra.get("observed_peaks", []),
                    "image_urls": image_urls,
                }
                yield f"data: {json.dumps(spectra_payload, ensure_ascii=False)}\n\n"
            except Exception:
                pass

            yield f"data: {json.dumps({'done': True, 'case_no': case_no}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/compare")
async def compare_spectra(
    current_user: CurrentUser,
    files: List[UploadFile] = File(...),
    analysis_type: str = Form("general"),
    material_hint: Optional[str] = Form(None),
    failure_background: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    多谱图并行对比分析：每张谱图独立调用 Claude，流式返回带 idx 标签的 SSE。

    SSE 格式：
      data: {"idx": 0, "content": "文本片段"}
      data: {"idx": 1, "content": "文本片段"}
      data: {"done": true, "case_nos": ["FA-2026-001", "FA-2026-002"]}
    """
    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    orchestrator = get_orchestrator()

    try:
        groups = await _extract_images_per_file(files, session_dir)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败：{e}")

    if not groups:
        raise HTTPException(status_code=400, detail="未找到有效的谱图图像")

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()
        n = len(groups)

        async def analyze_one(idx: int, paths: List[str]) -> None:
            full: List[str] = []
            try:
                async for chunk in orchestrator.analyze_stream(
                    images=paths,
                    analysis_type=analysis_type,
                    material_hint=material_hint,
                    failure_background=failure_background,
                ):
                    full.append(chunk)
                    await queue.put({"idx": idx, "content": chunk})
            except Exception as exc:
                await queue.put({"idx": idx, "error": str(exc)})
            await queue.put({"idx": idx, "_done": True, "text": "".join(full)})

        for i, g in enumerate(groups):
            asyncio.create_task(analyze_one(i, g))

        full_texts = [""] * n
        completed = 0
        while completed < n:
            item = await queue.get()
            if item.get("_done"):
                full_texts[item["idx"]] = item.get("text", "")
                completed += 1
            else:
                payload: dict = {"idx": item["idx"]}
                if "content" in item:
                    payload["content"] = item["content"]
                elif "error" in item:
                    payload["error"] = item["error"]
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        case_nos: List[Optional[str]] = []
        for g, text in zip(groups, full_texts):
            try:
                cn = _save_case(
                    db, g, analysis_type, material_hint, None, None, text, current_user.username
                )
                case_nos.append(cn)
            except Exception:
                case_nos.append(None)

        yield f"data: {json.dumps({'done': True, 'case_nos': case_nos}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _build_reference_context(material_ids: List[str], spec_type: str) -> tuple[List[dict], str]:
    """
    从知识库加载指定材料数据，格式化为参考文本，同时返回带 label 的材料列表。

    Returns:
        materials_info: [{"id": "PP", "label": "聚丙烯"}, ...]
        reference_context: 格式化后注入 prompt 的参考文本
    """
    from api.knowledge_db import _load_materials, _load_chemicals
    all_materials = _load_materials()
    all_chemicals = _load_chemicals()

    materials_info: List[dict] = []
    context_parts = ["参考材料数据库资料："]

    for mid in material_ids:
        entry = all_materials.get(mid) or all_chemicals.get(mid)
        if not entry:
            continue
        names = entry.get("common_names", [])
        label = names[0] if names else mid
        materials_info.append({"id": mid, "label": label})

        if spec_type == "ftir":
            peaks = entry.get("ftir_peaks", [])
            if peaks:
                peak_strs = "；".join(
                    f"{p['wavenumber']} cm⁻¹({p.get('assignment', '')}，{p.get('intensity', '')})"
                    for p in peaks[:15]
                )
                context_parts.append(f"【{mid} {label}】FTIR特征峰：{peak_strs}")
        elif spec_type == "dsc":
            params = entry.get("dsc_parameters", {})
            features = entry.get("dsc_features", [])
            lines = [f"【{mid} {label}】DSC参数："]
            if params.get("tm_range"):
                lines.append(f"  Tm范围：{params['tm_range']}°C")
            if params.get("tg_range"):
                lines.append(f"  Tg范围：{params['tg_range']}°C")
            if features:
                lines.append(f"  特征：{'; '.join(str(f) for f in features[:5])}")
            context_parts.append("\n".join(lines))
        elif spec_type == "tga":
            chars = entry.get("tga_characteristics", {})
            features = entry.get("tga_features", [])
            lines = [f"【{mid} {label}】TGA特征："]
            if chars.get("tga_onset_c"):
                lines.append(f"  起始分解温度：{chars['tga_onset_c']}°C")
            if chars.get("residue"):
                lines.append(f"  残留量：{chars['residue']}")
            if features:
                lines.append(f"  特征：{'; '.join(str(f) for f in features[:5])}")
            context_parts.append("\n".join(lines))

    return materials_info, "\n".join(context_parts)


@router.post("/cross-compare")
async def cross_compare(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    material_ids: str = Form(...),   # JSON 字符串，如 '["PP","PA6","ABS"]'
    spec_type: str = Form("ftir"),   # "ftir" | "dsc" | "tga"
    failure_background: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    跨材料对比：上传待测谱图 + 选择知识库参考材料，流式返回对比分析。

    SSE 格式：
      data: {"content": "文本片段"}
      data: {"type": "spectra_data", "mode": "cross_compare", "observed_peaks": [...],
             "standard_materials": [{"id": "PP", "label": "聚丙烯"}], "image_urls": [...]}
      data: {"done": true, "case_no": "FA-2026-xxx"}
    """
    try:
        ids: List[str] = json.loads(material_ids)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="material_ids 格式错误，应为 JSON 数组")

    if len(ids) < 1:
        raise HTTPException(status_code=400, detail="至少选择 1 种参考材料")
    if len(ids) > 5:
        raise HTTPException(status_code=400, detail="最多选择 5 种参考材料")
    if not all(isinstance(m, str) and m.strip() for m in ids):
        raise HTTPException(status_code=400, detail="material_ids 每项必须为非空字符串")

    session_id = str(uuid.uuid4())[:8]
    session_dir = UPLOAD_DIR / session_id
    orchestrator = get_orchestrator()

    try:
        image_paths = await _extract_images([file], session_dir)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败：{e}")

    if not image_paths:
        raise HTTPException(status_code=400, detail="未找到有效的谱图图像")

    materials_info, reference_context = _build_reference_context(ids, spec_type)
    if not materials_info:
        raise HTTPException(status_code=400, detail="未找到任何指定参考材料，请确认材料ID有效")

    async def event_stream():
        full_text: List[str] = []
        try:
            async for chunk in orchestrator.analyze_stream_cross_compare(
                images=image_paths,
                reference_context=reference_context,
                spec_type=spec_type,
                failure_background=failure_background,
            ):
                full_text.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

            case_no = _save_case(
                db, image_paths, f"cross_compare_{spec_type}",
                None, None, None,
                "".join(full_text), current_user.username,
            )

            try:
                spectra = await orchestrator.extract_peaks_structured(
                    image_paths,
                    "".join(full_text),
                )
                image_urls = [
                    f"/uploads/sessions/{session_id}/{Path(p).name}"
                    for p in image_paths
                ]
                spectra_payload = {
                    "type": "spectra_data",
                    "mode": "cross_compare",
                    "observed_peaks": spectra.get("observed_peaks", []),
                    "standard_materials": materials_info,
                    "image_urls": image_urls,
                }
                yield f"data: {json.dumps(spectra_payload, ensure_ascii=False)}\n\n"
            except Exception:
                pass

            yield f"data: {json.dumps({'done': True, 'case_no': case_no}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
