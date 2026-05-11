"""
分析案例记录路由
查询和管理历史失效分析案例
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.schemas import AnalysisCaseOut
from db.database import get_db
from db.models import AnalysisCase

router = APIRouter()


def _next_case_no(db: Session) -> str:
    """生成当年下一个案例编号，格式 FA-YYYY-NNN"""
    year = datetime.now().year
    prefix = f"FA-{year}-"
    last = (
        db.query(AnalysisCase)
        .filter(AnalysisCase.case_no.like(f"{prefix}%"))
        .order_by(AnalysisCase.case_no.desc())
        .first()
    )
    if last:
        seq = int(last.case_no.split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


@router.get("/", response_model=List[AnalysisCaseOut])
def list_cases(
    material_name: Optional[str] = None,
    confidence_level: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(AnalysisCase)
    if material_name:
        q = q.filter(AnalysisCase.material_name.ilike(f"%{material_name}%"))
    if confidence_level:
        q = q.filter(AnalysisCase.confidence_level == confidence_level)
    return q.order_by(AnalysisCase.created_at.desc()).all()


@router.get("/{case_no}", response_model=AnalysisCaseOut)
def get_case(case_no: str, db: Session = Depends(get_db)):
    case = db.query(AnalysisCase).filter(AnalysisCase.case_no == case_no).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"案例 {case_no} 不存在")
    return case


@router.delete("/{case_no}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_no: str, db: Session = Depends(get_db)):
    case = db.query(AnalysisCase).filter(AnalysisCase.case_no == case_no).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"案例 {case_no} 不存在")
    db.delete(case)
    db.commit()
