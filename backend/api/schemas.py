"""
API 请求/响应 Pydantic 模型
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── 标准谱图库 ──────────────────────────────────────────────

class StandardSpectrumCreate(BaseModel):
    material_name: str
    grade: Optional[str] = None
    supplier: Optional[str] = None
    approved_date: Optional[datetime] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    key_peaks: Optional[str] = None       # JSON 字符串
    key_thermal: Optional[str] = None     # JSON 字符串
    created_by: Optional[str] = None


class StandardSpectrumUpdate(BaseModel):
    material_name: Optional[str] = None
    grade: Optional[str] = None
    supplier: Optional[str] = None
    approved_date: Optional[datetime] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    key_peaks: Optional[str] = None
    key_thermal: Optional[str] = None


class StandardSpectrumOut(BaseModel):
    id: int
    material_name: str
    grade: Optional[str]
    supplier: Optional[str]
    approved_date: Optional[datetime]
    version: Optional[str]
    notes: Optional[str]
    ir_image_path: Optional[str]
    dsc_image_path: Optional[str]
    tga_image_path: Optional[str]
    key_peaks: Optional[str]
    key_thermal: Optional[str]
    created_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── 分析案例 ─────────────────────────────────────────────────

class AnalysisCaseOut(BaseModel):
    id: int
    case_no: str
    material_name: str
    failure_description: Optional[str]
    reference_source: Optional[str]
    conclusion: Optional[str]
    confidence_level: Optional[str]
    created_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
