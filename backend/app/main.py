from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.metrics import router as metrics_router
from app.api.incidents import router as incidents_router
from app.core.audit import init_db
from app.core.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Ransomware Backup Protection API",
    version="1.0.0",
    description="Защищённая система резервного копирования с детекцией ransomware",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(incidents_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
