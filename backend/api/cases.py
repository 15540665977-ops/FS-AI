"""
分析案例记录路由
查询和管理历史失效分析案例
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.schemas import AnalysisCaseOut
from core.security import CurrentAdmin, get_current_user
from db.database import get_db
from db.models import AnalysisCase

router = APIRouter(dependencies=[Depends(get_current_user)])


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


@router.get("/")
def list_cases(
    q: Optional[str] = None,
    material_name: Optional[str] = None,
    confidence_level: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(AnalysisCase)
    keyword = q or material_name
    if keyword:
        query = query.filter(
            AnalysisCase.material_name.ilike(f"%{keyword}%")
            | AnalysisCase.case_no.ilike(f"%{keyword}%")
        )
    if confidence_level:
        query = query.filter(AnalysisCase.confidence_level == confidence_level)
    query = query.order_by(AnalysisCase.created_at.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return {
        "items": [AnalysisCaseOut.model_validate(c) for c in items],
        "total": total,
    }


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
