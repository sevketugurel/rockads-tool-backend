from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from infrastructure.database.models import Base
from core.config.settings import settings
import os


DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)
ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL", settings.async_database_url)

# SQLite için connect_args gerekli
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
async_engine = create_async_engine(ASYNC_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False
)


async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Ensure new columns exist for backward compatibility (SQLite lacks migrations)
        # Add target_countries to localization_jobs if missing
        try:
            result = await conn.exec_driver_sql("PRAGMA table_info('localization_jobs');")
            cols = [row[1] for row in result.fetchall()]
            if 'target_countries' not in cols:
                await conn.exec_driver_sql("ALTER TABLE localization_jobs ADD COLUMN target_countries JSON;")
        except Exception:
            # Non-critical: skip if fails
            pass

        # Helpful index to reduce duplicates and speed lookups
        try:
            await conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_translations_video_country ON translations (video_id, country_id);"
            )
        except Exception:
            pass
