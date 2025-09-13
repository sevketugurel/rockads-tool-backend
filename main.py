from fastapi import FastAPI
from contextlib import asynccontextmanager
from infrastructure.database.connection import create_tables
from presentation.api import user_routes, item_routes, video_routes, localization_routes
from presentation.middleware.cors import add_cors_middleware
from core.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

add_cors_middleware(app)

app.include_router(user_routes.router)
app.include_router(item_routes.router)
app.include_router(video_routes.router)
app.include_router(localization_routes.router)


@app.get("/")
async def root():
    return {"message": "FastAPI Clean Architecture Backend", "version": settings.app_version}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )