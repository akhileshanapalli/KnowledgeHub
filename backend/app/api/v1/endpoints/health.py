import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from app.config import settings

router = APIRouter()


@router.get("/health", status_code=200)
def health_check(db: Session = Depends(get_db)):
    start = time.perf_counter()
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1;"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    total_latency_ms = (time.perf_counter() - start) * 1000

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "latency_ms": round(total_latency_ms, 2),
    }
