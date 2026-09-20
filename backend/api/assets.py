"""Authenticated delivery of uploaded spectra and generated images."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.paths import UPLOADS_DIR
from core.security import CurrentUser

router = APIRouter()
_UPLOADS_DIR = UPLOADS_DIR


@router.get("/{asset_path:path}")
def download_upload(asset_path: str, _: CurrentUser):
    candidate = (_UPLOADS_DIR / asset_path).resolve()
    try:
        candidate.relative_to(_UPLOADS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="文件不存在")

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(candidate)
