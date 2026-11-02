"""应用配置：全部来自 backend/.env。

部署约定：后端可能随现场变化的配置项统一放在 backend/.env；
前端（底图等）配置统一放在 web/public/js/config.js，两边互不引用。
"""
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend 目录（config.py -> core -> app -> backend）
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # 用绝对路径：以 Windows 服务/计划任务方式启动时工作目录不是 backend，
        # 相对路径会读不到 .env
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 服务监听 ----
    app_host: str = "0.0.0.0"
    app_port: int = 8100

    # ---- 数据库 ----
    pg_host: str = "127.0.0.1"
    pg_port: int = 5432
    pg_db: str = "plains"
    pg_user: str = "postgres"
    pg_password: str = ""

    # ---- 鉴权 ----
    jwt_secret: str = "dev-secret"
    jwt_expire_minutes: int = 720

    # ---- 空间参数 ----
    # PostGIS 几何列 SRID：4490=CGCS2000，4326=WGS84。
    # 这是数据库表结构级参数，改了必须同步重建几何列，故放在 .env 而非 sys_config。
    spatial_srid: int = 4490
    map_center_lng: float | None = None
    map_center_lat: float | None = None
    map_default_zoom: int = 16

    # ---- 经纬度比对 ----
    compare_default_threshold_m: float = 10.0

    # ---- 跨域 ----
    cors_origins: str = "*"

    # ---- 外景影像上传 ----
    upload_dir: str = "uploads"
    upload_url_prefix: str = "/api/uploads"
    facade_max_upload_mb: int = 60
    facade_thumb_size: int = 720

    # ---- 前端静态资源（构建产物）----
    web_dist: str = "../web/dist"

    @property
    def web_dist_path(self) -> Path:
        """前端构建产物目录（相对路径以 backend 目录为基准）。"""
        path = Path(self.web_dist)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @property
    def upload_root(self) -> Path:
        """上传根目录（相对路径以 backend 目录为基准）。"""
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @property
    def database_url(self) -> str:
        # 口令里可能含 @ / : 等字符，必须转义后再拼连接串
        return (
            f"postgresql+psycopg://{self.pg_user}:{quote_plus(self.pg_password)}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    @property
    def origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
