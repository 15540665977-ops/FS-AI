"""Session login and administrator account-management routes."""
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.schemas import LoginRequest, PasswordResetRequest, UserCreate, UserOut
from core.security import CurrentAdmin, CurrentUser, hash_password, validate_password, verify_password
from db.database import get_db
from db.models import User

router = APIRouter()
_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not _USERNAME_RE.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="用户名须为 3–64 个字符，只能使用字母、数字、句点、下划线或连字符",
        )
    return normalized


def create_initial_admin(db: Session) -> None:
    """Create the bootstrap admin only when the database has no accounts."""
    if db.query(User.id).first():
        return

    username = os.environ.get("INITIAL_ADMIN_USERNAME")
    password = os.environ.get("INITIAL_ADMIN_PASSWORD")
    if not username or not password:
        return

    username = normalize_username(username)
    validate_password(password)
    db.add(User(username=username, password_hash=hash_password(password), is_admin=True))
    db.commit()
    print(f"已创建初始管理员账户：{username}")


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    username = normalize_username(payload.username)
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    request.session.clear()
    request.session["user_id"] = user.id
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request):
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def get_me(current_user: CurrentUser):
    return current_user


@router.get("/users", response_model=list[UserOut])
def list_users(_: CurrentAdmin, db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.asc()).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, _: CurrentAdmin, db: Session = Depends(get_db)):
    username = normalize_username(payload.username)
    validate_password(payload.password)
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    db.refresh(user)
    return user


@router.put("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
):
    validate_password(payload.password)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.password_hash = hash_password(payload.password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/users/{user_id}/active", response_model=UserOut)
def set_user_active(
    user_id: int,
    is_active: bool,
    current_admin: CurrentAdmin,
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.id == current_admin.id and not is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用当前登录账户")
    if user.is_admin and user.is_active and not is_active:
        active_admin_count = db.query(func.count(User.id)).filter(
            User.is_admin.is_(True), User.is_active.is_(True)
        ).scalar()
        if active_admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少保留一个活跃管理员")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user
