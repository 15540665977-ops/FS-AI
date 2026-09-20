"""
API 请求/响应 Pydantic 模型
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


# ── 身份认证 ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=10, max_length=256)
    is_admin: bool = False


class PasswordResetRequest(BaseModel):
    password: str = Field(min_length=10, max_length=256)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


# ── 分析案例 ─────────────────────────────────────────────────

class AnalysisCaseOut(BaseModel):
    id: int
    case_no: str
    material_name: str
    failure_description: Optional[str]
    reference_source: Optional[str]
    uploaded_files: Optional[str]      # JSON 字符串，文件路径列表
    analysis_result: Optional[str]     # 完整 AI 分析报告
    conclusion: Optional[str]          # 末尾摘要（最多500字）
    confidence_level: Optional[str]
    created_by: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
