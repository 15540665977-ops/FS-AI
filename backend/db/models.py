"""
SQLAlchemy 数据模型定义
"""
from sqlalchemy import Boolean, Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    """Application account used for session authentication."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class StandardSpectrum(Base):
    """
    标准谱图档案表
    存储经过认可的标准谱图数据，包括 FTIR、DSC、TGA 等测试结果
    """
    __tablename__ = "standard_spectra"

    id = Column(Integer, primary_key=True, index=True)
    material_name = Column(String(255), nullable=False, index=True)  # 材料名称
    grade = Column(String(255), nullable=True)  # 牌号/等级
    supplier = Column(String(255), nullable=True)  # 供应商
    approved_date = Column(DateTime, nullable=True)  # 认可日期
    version = Column(String(50), nullable=True)  # 版本号
    notes = Column(Text, nullable=True)  # 备注说明

    # 谱图图像路径
    ir_image_path = Column(String(500))  # FTIR 红外光谱图
    dsc_image_path = Column(String(500))  # DSC 差示扫描量热图
    tga_image_path = Column(String(500))  # TGA 热重分析图

    # 关键特征数据（JSON 字符串存储）
    key_peaks = Column(Text, nullable=True)  # 关键峰位 JSON: [{"wavenumber": 1735, "assignment": "C=O", "intensity": "强"}]
    key_thermal = Column(Text, nullable=True)  # 热参数 JSON: {"tm": 165.2, "tg": -12.5, "delta_h": 85.3}

    created_by = Column(String(100), nullable=True)  # 录入人
    created_at = Column(DateTime, default=datetime.now)  # 创建时间

    # 关联关系
    analysis_cases = relationship("AnalysisCase", back_populates="standard_spectrum")


class AnalysisCase(Base):
    """
    分析案例记录表
    存储每次失效分析或一致性检验的完整记录
    """
    __tablename__ = "analysis_cases"

    id = Column(Integer, primary_key=True, index=True)
    case_no = Column(String(50), unique=True, nullable=False, index=True)  # 案例编号：FA-YYYY-NNN

    # 基本信息
    material_name = Column(String(255), nullable=False)  # 材料名称
    failure_description = Column(Text, nullable=True)  # 失效描述
    created_by = Column(String(100), nullable=True)  # 分析人
    created_at = Column(DateTime, default=datetime.now)  # 创建时间

    # 上传文件列表（JSON 存储路径）
    uploaded_files = Column(Text, nullable=True)  # [{"original_name": "...", "file_path": "..."}]

    # 参考来源
    reference_source = Column(String(50), nullable=True)  # "library" | "manual_upload" | "none"
    reference_id = Column(Integer, ForeignKey("standard_spectra.id"), nullable=True)  # 关联标准谱图 ID

    # AI 分析结果（JSON 存储完整对话）
    analysis_result = Column(Text, nullable=True)  # {"messages": [...], "conclusion": "..."}
    conclusion = Column(Text, nullable=True)  # 最终结论文本
    confidence_level = Column(String(20), nullable=True)  # "high" | "medium" | "low" | "unknown"

    # 关联关系
    standard_spectrum = relationship("StandardSpectrum", back_populates="analysis_cases")


def create_tables():
    from .database import engine
    Base.metadata.create_all(bind=engine)
