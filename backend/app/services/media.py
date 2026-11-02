"""外景影像文件存储：落盘、缩略图、EXIF 解析。

说明：缩略图与 EXIF 依赖 Pillow，未安装时自动降级（照常保存原图，仅缺缩略图）。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger("plains.media")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MODEL_EXTS = {".glb", ".gltf", ".zip"}

_CHUNK = 1024 * 1024


def upload_root() -> Path:
    root = settings.upload_root
    root.mkdir(parents=True, exist_ok=True)
    return root


def file_url(rel_path: str | None) -> str | None:
    """把相对存储路径转换成浏览器可访问的 URL。"""
    if not rel_path:
        return None
    prefix = settings.upload_url_prefix.rstrip("/")
    return f"{prefix}/{rel_path.lstrip('/')}"


def save_upload(upload: UploadFile, building_id: int, kind: str) -> dict[str, Any]:
    """保存单个上传文件，返回写库所需的字段。"""
    name = Path(upload.filename or "file").name
    ext = Path(name).suffix.lower()
    if kind == "model":
        if ext not in MODEL_EXTS:
            raise AppError(f"三维模型仅支持 {', '.join(sorted(MODEL_EXTS))} 格式")
    elif ext not in IMAGE_EXTS:
        raise AppError(f"外景影像仅支持 {', '.join(sorted(IMAGE_EXTS))} 格式")

    root = upload_root()
    rel_dir = Path("facade") / str(building_id)
    (root / rel_dir).mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    rel_path = (rel_dir / f"{uid}{ext}").as_posix()
    target = root / rel_path

    max_bytes = max(settings.facade_max_upload_mb, 1) * 1024 * 1024
    size = 0
    try:
        with target.open("wb") as fh:
            while True:
                chunk = upload.file.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(f"文件超过 {settings.facade_max_upload_mb}MB 上限：{name}")
                fh.write(chunk)
    except AppError:
        target.unlink(missing_ok=True)
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise AppError(f"文件保存失败：{exc}") from exc
    finally:
        upload.file.close()

    if size == 0:
        target.unlink(missing_ok=True)
        raise AppError(f"文件内容为空：{name}")

    info: dict[str, Any] = {
        "file_name": name,
        "file_path": rel_path,
        "mime": upload.content_type,
        "file_size": size,
        "thumb_path": None,
        "width": None,
        "height": None,
        "taken_at": None,
        "lng": None,
        "lat": None,
        "extra": None,
    }
    if kind != "model":
        info.update(_inspect_image(root, rel_path, uid))
    return info


def delete_files(*rel_paths: str | None) -> None:
    """删除影像文件；路径必须落在上传根目录内，避免越权删除。"""
    root = upload_root().resolve()
    for rel in rel_paths:
        if not rel:
            continue
        target = (root / rel).resolve()
        if target == root or root not in target.parents:
            continue
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover
            logger.warning("删除文件失败 %s: %s", rel, exc)


def _inspect_image(root: Path, rel_path: str, uid: str) -> dict[str, Any]:
    """读取尺寸 / EXIF / 生成缩略图；任何异常都不影响原图入库。"""
    try:
        from PIL import Image, ImageOps
    except ImportError:  # pragma: no cover - 依赖缺失时降级
        logger.warning("未安装 Pillow，跳过缩略图与 EXIF 解析")
        return {}

    result: dict[str, Any] = {}
    try:
        with Image.open(root / rel_path) as img:
            result["width"], result["height"] = img.size
            exif = _safe_exif(img)
            if exif:
                taken = exif.get(36867) or exif.get(306)
                if taken:
                    parsed = _parse_exif_time(taken)
                    if parsed:
                        result["taken_at"] = parsed
                gps = _gps_of(exif)
                if gps:
                    result["lat"], result["lng"] = gps
            result["extra"] = {"format": img.format, "mode": img.mode}

            thumb = ImageOps.exif_transpose(img).convert("RGB")
            thumb.thumbnail((settings.facade_thumb_size, settings.facade_thumb_size))
            thumb_dir = root / "facade" / "thumbs"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            thumb_rel = f"facade/thumbs/{uid}.jpg"
            thumb.save(root / thumb_rel, "JPEG", quality=82, optimize=True)
            result["thumb_path"] = thumb_rel
    except Exception as exc:  # noqa: BLE001 - 解析失败不应阻断上传
        logger.warning("图片解析失败 %s: %s", rel_path, exc)
    return result


def _safe_exif(img: Any) -> Any:
    try:
        return img.getexif()
    except Exception:  # noqa: BLE001
        return None


def _parse_exif_time(value: Any) -> datetime | None:
    text = str(value).strip()[:19]
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _to_degrees(values: Any) -> float | None:
    try:
        deg, minute, second = (float(v) for v in values)
    except (TypeError, ValueError):
        return None
    return deg + minute / 60 + second / 3600


def _gps_of(exif: Any) -> tuple[float, float] | None:
    """返回 (纬度, 经度)。"""
    try:
        gps = exif.get_ifd(34853)
    except Exception:  # noqa: BLE001
        return None
    if not gps:
        return None
    lat = _to_degrees(gps.get(2))
    lon = _to_degrees(gps.get(4))
    if lat is None or lon is None:
        return None
    if gps.get(1) in ("S", b"S"):
        lat = -lat
    if gps.get(3) in ("W", b"W"):
        lon = -lon
    return lat, lon
