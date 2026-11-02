"""统一启动入口：python serve.py

监听地址与端口取自 backend/.env 的 APP_HOST / APP_PORT，
等价于：uvicorn app.main:app --host 0.0.0.0 --port 8100
"""
import sys
from pathlib import Path

import uvicorn

# 确保以任意工作目录启动（Windows 服务 / 计划任务）都能 import app 包
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import settings  # noqa: E402

if __name__ == "__main__":
    print(f"服务启动：http://{settings.app_host}:{settings.app_port}")
    print(f"前端目录：{settings.web_dist_path}")
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level="info",
        access_log=False,
    )
