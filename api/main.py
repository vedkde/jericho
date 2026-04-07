import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from api.routes_env import router as env_router
from api.routes_tasks import router as tasks_router
from api.routes_grader import router as grader_router
from api.routes_baseline import router as baseline_router

app = FastAPI(
    title="Code Debugging Environment",
    description="An OpenEnv-compatible environment where AI agents fix buggy code.",
    version="1.0.0"
)

# prefixed routes (original)
app.include_router(env_router,      prefix="/env",      tags=["Environment"])
app.include_router(tasks_router,    prefix="/tasks",    tags=["Tasks"])
app.include_router(grader_router,   prefix="/grader",   tags=["Grader"])
app.include_router(baseline_router, prefix="/baseline", tags=["Baseline"])

# root-level routes (for OpenEnv checker)
app.include_router(env_router,   tags=["OpenEnv"])
app.include_router(tasks_router, tags=["OpenEnv"])
app.include_router(grader_router, tags=["OpenEnv"])

@app.get("/")
def root():
    return {
        "status": "ok",
        "endpoints": ["/tasks", "/env/reset", "/env/step", "/env/state", "/grader", "/baseline",
                      "/reset", "/step", "/state"]
    }
