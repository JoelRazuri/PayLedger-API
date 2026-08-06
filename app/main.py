from fastapi import FastAPI

from app.core.settings import get_settings
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API for payment reconciliation and ledger management",
)

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }
