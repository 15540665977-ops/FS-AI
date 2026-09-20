"""
标准谱图库路由
管理认可的 FTIR/DSC/TGA 标准谱图档案
"""
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.schemas import StandardSpectrumCreate, StandardSpectrumOut, StandardSpectrumUpdate
from core.paths import UPLOADS_DIR
from core.security import CurrentAdmin, get_current_user
from db.database import get_db
from db.models import StandardSpectrum

router = APIRouter(dependencies=[Depends(get_current_user)])

UPLOAD_DIR = UPLOADS_DIR / "library"


@router.get("/", response_model=List[StandardSpectrumOut])
def list_spectra(
    material_name: Optional[str] = None,
    supplier: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(StandardSpectrum)
    if material_name:
        q = q.filter(StandardSpectrum.material_name.ilike(f"%{material_name}%"))
    if supplier:
        q = q.filter(StandardSpectrum.supplier.ilike(f"%{supplier}%"))
    return q.order_by(StandardSpectrum.created_at.desc()).all()


@router.post("/", response_model=StandardSpectrumOut, status_code=status.HTTP_201_CREATED)
def create_spectrum(
    payload: StandardSpectrumCreate,
    current_admin: CurrentAdmin,
    db: Session = Depends(get_db),
):
    spectrum = StandardSpectrum(**payload.model_dump(exclude={"created_by"}), created_by=current_admin.username)
    db.add(spectrum)
    db.commit()
    db.refresh(spectrum)
    return spectrum


@router.get("/{spectrum_id}", response_model=StandardSpectrumOut)
def get_spectrum(spectrum_id: int, db: Session = Depends(get_db)):
    spectrum = db.query(StandardSpectrum).filter(StandardSpectrum.id == spectrum_id).first()
    if not spectrum:
        raise HTTPException(status_code=404, detail="谱图档案不存在")
    return spectrum


@router.put("/{spectrum_id}", response_model=StandardSpectrumOut)
def update_spectrum(
    spectrum_id: int,
    payload: StandardSpectrumUpdate,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
):
    spectrum = db.query(StandardSpectrum).filter(StandardSpectrum.id == spectrum_id).first()
    if not spectrum:
        raise HTTPException(status_code=404, detail="谱图档案不存在")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(spectrum, field, value)
    db.commit()
    db.refresh(spectrum)
    return spectrum


@router.delete("/{spectrum_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spectrum(
    spectrum_id: int,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
):
    spectrum = db.query(StandardSpectrum).filter(StandardSpectrum.id == spectrum_id).first()
    if not spectrum:
        raise HTTPException(status_code=404, detail="谱图档案不存在")
    db.delete(spectrum)
    db.commit()


@router.post("/{spectrum_id}/images", response_model=StandardSpectrumOut)
async def upload_spectrum_images(
    spectrum_id: int,
    _: CurrentAdmin,
    ir_image: Optional[UploadFile] = File(None),
    dsc_image: Optional[UploadFile] = File(None),
    tga_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """上传 FTIR/DSC/TGA 谱图图像到指定档案"""
    spectrum = db.query(StandardSpectrum).filter(StandardSpectrum.id == spectrum_id).first()
    if not spectrum:
        raise HTTPException(status_code=404, detail="谱图档案不存在")

    save_dir = UPLOAD_DIR / str(spectrum_id)
    save_dir.mkdir(parents=True, exist_ok=True)

    for file_field, attr in [
        (ir_image, "ir_image_path"),
        (dsc_image, "dsc_image_path"),
        (tga_image, "tga_image_path"),
    ]:
        if file_field:
            suffix = Path(file_field.filename or "").suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise HTTPException(status_code=415, detail="标准谱图仅支持 PNG、JPG、JPEG 或 WEBP 图片")
            dest = save_dir / f"{attr}{suffix}"
            with open(dest, "wb") as f:
                shutil.copyfileobj(file_field.file, f)
            setattr(spectrum, attr, str(dest))

    db.commit()
    db.refresh(spectrum)
    return spectrum
