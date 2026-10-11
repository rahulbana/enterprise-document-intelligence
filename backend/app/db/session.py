# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# SQLAlchemy engine and session factory, built from Settings.DATABASE_URL.
#
# Pooling (Phase 7): SQLite is a single on-disk file with no server-side
# connection concept, so QueuePool sizing is meaningless for it and
# SQLAlchemy's own sqlite dialect already picks an appropriate pool
# (NullPool/SingletonThreadPool) — passing pool_size/max_overflow to it
# raises. Those knobs apply once DATABASE_URL points at Postgres (Phase 8);
# pool_pre_ping is cheap and safe for both, so it's always on.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if _is_sqlite else {}
pool_kwargs = (
    {}
    if _is_sqlite
    else {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
    }
)

engine = create_engine(
    settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, **pool_kwargs
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
