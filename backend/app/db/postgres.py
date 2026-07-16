from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.models import Base


def _clean_async_url(url: str) -> str:
    async_url = url.replace("postgresql://", "postgresql+asyncpg://")
    parsed = urlparse(async_url)
    params = parse_qs(parsed.query)
    params.pop("sslmode", None)
    params.pop("channel_binding", None)
    clean_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.async_session = None

    async def initialize(self):
        async_url = _clean_async_url(settings.neon_db_url)
        self.engine = create_async_engine(async_url, poolclass=NullPool)
        self.async_session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        return self.async_session()

    async def close(self):
        if self.engine:
            await self.engine.dispose()


db_manager = DatabaseManager()
