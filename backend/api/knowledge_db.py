"""
知识库查询路由
直接从 JSON 源文件返回材料/化学品峰数据，供前端 IR 曲线查看器使用
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

_KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

# ── 材料类型 → (中文子类, 大类) ──────────────────────────────────
_MAT_TYPE_MAP: dict[str, tuple[str, str]] = {
    "polyolefin":            ("聚烯烃",       "塑料"),
    "polyolefin_composite":  ("聚烯烃复合",   "塑料"),
    "engineering_plastic":   ("工程塑料",     "塑料"),
    "polyamide":             ("聚酰胺(尼龙)", "塑料"),
    "acrylic":               ("丙烯酸类",     "塑料"),
    "styrene_polymer":       ("苯乙烯类",     "塑料"),
    "vinyl":                 ("乙烯基/PVC",   "塑料"),
    "high_performance_plastic": ("高性能塑料","塑料"),
    "fluoropolymer":         ("氟聚合物",     "塑料"),
    "alloy":                 ("合金/共混",    "塑料"),
    "copolymer":             ("共聚物",       "塑料"),
    "elastomer":             ("通用橡胶",     "橡胶/弹性体"),
    "elastomer_alloy":       ("橡胶合金",     "橡胶/弹性体"),
    "fluoroelastomer":       ("氟橡胶",       "橡胶/弹性体"),
    "silicone_elastomer":    ("硅橡胶",       "橡胶/弹性体"),
    "elastomer_modifier":    ("弹性体改性剂", "橡胶/弹性体"),
    "thermoplastic_elastomer": ("热塑性弹性体", "热塑弹性体"),
}

# ── 化学品 category → (中文子类, 大类) ─────────────────────────────
_CHEM_TYPE_MAP: dict[str, tuple[str, str]] = {
    "plasticizer":            ("增塑剂",     "添加剂"),
    "plasticizer_stabilizer": ("增塑剂",     "添加剂"),
    "antioxidant":            ("抗氧剂",     "添加剂"),
    "filler":                 ("填料",       "添加剂"),
    "pigment_filler":         ("填料/颜料",  "添加剂"),
    "pigment_filler_conductive": ("填料/颜料", "添加剂"),
    "lubricant":              ("润滑/稳定剂","添加剂"),
    "lubricant_processing_aid":  ("润滑/稳定剂","添加剂"),
    "lubricant_heat_stabilizer": ("润滑/稳定剂","添加剂"),
    "light_stabilizer":       ("光稳定剂",   "添加剂"),
    "uv_stabilizer":          ("光稳定剂",   "添加剂"),
    "flame_retardant":        ("阻燃剂",     "添加剂"),
    "coupling_agent":         ("偶联剂",     "添加剂"),
    "elastomer_modifier":     ("弹性体改性剂","添加剂"),
    "contaminant":            ("污染物",     "污染物/降解"),
    "contaminant_lubricant":  ("污染物",     "污染物/降解"),
    "contaminant_environmental": ("污染物",  "污染物/降解"),
    "degradation":            ("降解产物",   "污染物/降解"),
    "degradation_product":    ("降解产物",   "污染物/降解"),
}


@lru_cache(maxsize=1)
def _load_materials() -> dict:
    # 缓存至进程重启为止；知识库 JSON 文件视为只读，运行时修改需重启服务生效
    path = _KNOWLEDGE_DIR / "materials.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@lru_cache(maxsize=1)
def _load_chemicals() -> dict:
    # 同上
    path = _KNOWLEDGE_DIR / "chemicals.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@router.get("/entries")
def list_entries(search: Optional[str] = Query(None)):
    """返回所有条目摘要（含两级分类标签，供侧边栏筛选使用）"""
    results = []

    for entry_id, mat in _load_materials().items():
        names = mat.get("common_names", [])
        mt = mat.get("material_type", "")
        display_group, super_group = _MAT_TYPE_MAP.get(mt, (mt or "其他", "塑料"))
        results.append({
            "id": entry_id,
            "label": names[0] if names else entry_id,
            "aliases": names,
            "display_group": display_group,
            "super_group": super_group,
            "source": "materials",
            "peak_count": len(mat.get("ftir_peaks", [])),
        })

    for entry_id, chem in _load_chemicals().items():
        names = chem.get("common_names", [])
        cat = chem.get("category", "")
        display_group, super_group = _CHEM_TYPE_MAP.get(cat, (cat or "其他", "添加剂"))
        results.append({
            "id": entry_id,
            "label": names[0] if names else entry_id,
            "aliases": names,
            "display_group": display_group,
            "super_group": super_group,
            "source": "chemicals",
            "peak_count": len(chem.get("ftir_peaks", [])),
        })

    if search:
        q = search.strip().lower()
        results = [
            r for r in results
            if q in r["id"].lower()
            or q in r["label"].lower()
            or any(q in a.lower() for a in r["aliases"])
        ]

    return results


@router.get("/entry/{entry_id}")
def get_entry(entry_id: str):
    """返回单个条目的详细峰数据（用于绘制 IR 曲线）"""
    materials = _load_materials()
    if entry_id in materials:
        mat = materials[entry_id]
        mt = mat.get("material_type", "")
        display_group, super_group = _MAT_TYPE_MAP.get(mt, (mt or "其他", "塑料"))
        return {
            "id": entry_id,
            "source": "materials",
            "common_names": mat.get("common_names", []),
            "display_group": display_group,
            "super_group": super_group,
            "ftir_peaks": mat.get("ftir_peaks", []),
            "dsc_parameters": mat.get("dsc_parameters", {}),
            "dsc_features": mat.get("dsc_features", []),
            "tga_characteristics": mat.get("tga_characteristics", {}),
            "tga_features": mat.get("tga_features", []),
            "automotive_additives": mat.get("automotive_additives", None),
            "notes": mat.get("鉴别要点", ""),
            "confusions": mat.get("常见混淆", ""),
        }

    chemicals = _load_chemicals()
    if entry_id in chemicals:
        chem = chemicals[entry_id]
        cat = chem.get("category", "")
        display_group, super_group = _CHEM_TYPE_MAP.get(cat, (cat or "其他", "添加剂"))
        return {
            "id": entry_id,
            "source": "chemicals",
            "common_names": chem.get("common_names", []),
            "display_group": display_group,
            "super_group": super_group,
            "ftir_peaks": chem.get("ftir_peaks", []),
            "notes": chem.get("识别特征", ""),
            "application": chem.get("应用场景", ""),
            "host_materials": chem.get("常见宿主材料", []),
        }

    raise HTTPException(status_code=404, detail=f"未找到条目：{entry_id}")
