from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config import settings

_engine = None
_maker = None

def get_engine():
    global _engine, _maker
    if _engine is None:  # ленивое подключение: import main не падает без БД
        _engine = create_async_engine(settings.db_url, pool_pre_ping=True)
        _maker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine

async def get_session():
    get_engine()
    async with _maker() as s:
        yield s

def session_maker():
    get_engine()
    return _maker
