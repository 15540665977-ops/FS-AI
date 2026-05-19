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
from core.file_parser import process_pdf_file
from db.database import get_db
from db.models import AnalysisCase, StandardSpectrum

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "sessions"

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
    image_paths = []

    for file in files:
        filename = file.filename or "upload"
        ext = Path(filename).suffix.lower()
        content = await file.read()

        if ext == ".pdf":
            pdf_obj = io.BytesIO(content)
            paths = process_pdf_file(pdf_obj, session_dir)
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
    groups: List[List[str]] = []
    for file in files:
        filename = file.filename or "upload"
        ext = Path(filename).suffix.lower()
        content = await file.read()
        paths: List[str] = []
        if ext == ".pdf":
            paths = process_pdf_file(io.BytesIO(content), session_dir)
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


def _save_case(
    db: Session,
    image_paths: List[str],
    analysis_type: str,
    material_hint: Optional[str],
    reference_source: Optional[str],
    reference_id: Optional[int],
    full_text: str,
) -> str:
    """分析完成后将结果保存为案例记录，返回案例编号"""
    from api.cases import _next_case_no
    case_no = _next_case_no(db)
    case = AnalysisCase(
        case_no=case_no,
        material_name=material_hint or "未知",
        failure_description=f"分析类型：{analysis_type}",
        uploaded_files=json.dumps(image_paths),
        reference_source=reference_source,
        reference_id=reference_id,
        analysis_result=full_text,
        conclusion=full_text[-500:] if full_text else "",
        confidence_level="unknown",
    )
    db.add(case)
    db.commit()
    return case_no


@router.post("/stream")
async def analyze_stream(
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
                "".join(full_text),
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
                cn = _save_case(db, g, analysis_type, material_hint, None, None, text)
                case_nos.append(cn)
            except Exception:
                case_nos.append(None)

        yield f"data: {json.dumps({'done': True, 'case_nos': case_nos}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
