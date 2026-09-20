"""
SQLite 数据库连接配置
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.paths import DATABASE_PATH


DATABASE_URL = os.environ.get(
    "SPECTRAL_DATABASE_URL",
    f"sqlite:///{DATABASE_PATH.as_posix()}",
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 声明基类
class Base(DeclarativeBase):
    pass


def get_db():
    """
    依赖注入：为每个请求创建数据库会话
    使用 try/finally 确保会话在使用后关闭
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
