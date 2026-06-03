from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.metrics import router as metrics_router
from app.api.incidents import router as incidents_router

app = FastAPI(
    title="Ransomware Backup Protection API",
    version="1.0.0",
    description="Защищённая система резервного копирования с детекцией ransomware",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(incidents_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
