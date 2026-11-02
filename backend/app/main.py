"""一标六实数据采集系统 后端入口。"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import AppError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("plains")

app = FastAPI(
    title="一标六实数据采集系统",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "data": exc.data},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": f"参数错误：{loc} {first.get('msg', '')}", "data": None},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None},
    )


@app.get("/api/health", tags=["系统"])
def health() -> dict:
    return {"code": 0, "message": "ok", "data": {"app": "plains", "status": "up"}}


app.include_router(api_router, prefix="/api/v1")

# 外景影像等上传文件：/api/uploads/... 由后端直接托管（前端经 /api 代理访问）
upload_root = settings.upload_root
upload_root.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(upload_root)), name="uploads")


class SPAStaticFiles(StaticFiles):
    """前端构建产物托管：未知路径回退 index.html；/api 下保持 404，避免吞掉接口错误。"""

    async def __call__(self, scope, receive, send):  # type: ignore[override]
        # 挂载在 / 上会兜住所有请求，接口前缀必须直接返回 404，不能回退成页面
        if scope.get("type") == "http" and str(scope.get("path", "")).lstrip("/").startswith("api/"):
            response = JSONResponse(
                {"code": 404, "message": "接口不存在", "data": None}, status_code=404
            )
            await response(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.lstrip("/").startswith("api/"):
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and not path.lstrip("/").startswith("api/"):
            return await super().get_response("index.html", scope)
        return response


# 页面与后端起在同一端口：直接访问 http://<host>:8100/ 即可打开系统
web_dist = settings.web_dist_path
if (web_dist / "index.html").is_file():
    app.mount("/", SPAStaticFiles(directory=str(web_dist), html=True), name="web")
    logger.info("前端静态资源目录：%s", web_dist)
else:
    logger.warning(
        "未找到前端构建产物（%s），当前仅提供 API；如需同端口访问页面请先执行前端构建",
        web_dist,
    )
