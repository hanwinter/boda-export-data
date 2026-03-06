from __future__ import annotations

import uvicorn

from app.core.settings import load_app_config
from app.main import app as fastapi_app


if __name__ == "__main__":
    cfg = load_app_config()
    uvicorn.run(fastapi_app, host=cfg.host, port=cfg.port, reload=False)
