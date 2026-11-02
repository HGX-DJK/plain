"""建筑物外景采集：外景照片 / 360 全景 / 三维模型的上传与影像库管理。"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.deps import client_ip, require_permissions
from app.core.errors import AppError, NotFound, ok, page_ok
from app.db.session import get_db
from app.models.building import Building
from app.models.facade import FACADE_DIRECTIONS, FACADE_KINDS, FacadeMedia
from app.models.system import User
from app.schemas.common import IdsPayload, PageParams
from app.schemas.facade import FacadeOut, FacadeUpdate
from app.services import media as media_svc
from app.services.audit import log_action

router = APIRouter(prefix="/facade", tags=["建筑物外景"])

guard_view = require_permissions("facade:view", "building:view")
guard_create = require_permissions("facade:create", "building:update")
guard_update = require_permissions("facade:update", "building:update")
guard_delete = require_permissions("facade:delete", "building:update")


def _out(media: FacadeMedia) -> dict[str, Any]:
    data = FacadeOut.model_validate(media).model_dump(mode="json")
    data["url"] = media_svc.file_url(media.file_path)
    data["thumb_url"] = media_svc.file_url(media.thumb_path) or data["url"]
    data["facade_label"] = FACADE_DIRECTIONS.get(media.facade, media.facade)
    data["kind_label"] = FACADE_KINDS.get(media.kind, media.kind)
    return data


def _check_kind(kind: str) -> str:
    if kind not in FACADE_KINDS:
        raise AppError(f"不支持的影像类别：{kind}")
    return kind


def _check_facade(facade: str) -> str:
    if facade not in FACADE_DIRECTIONS:
        raise AppError(f"不支持的立面方位：{facade}")
    return facade


def _parse_dt(text: str | None) -> datetime | None:
    if not text or not text.strip():
        return None
    try:
        return datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppError("拍摄时间格式不正确，应为 2024-05-01 10:00:00") from exc


def _get_media(db: Session, media_id: int) -> FacadeMedia:
    media = db.get(FacadeMedia, media_id)
    if media is None:
        raise NotFound("外景影像不存在")
    return media


@router.get("/buildings")
def building_options(
    keyword: str | None = Query(None, description="名称/编码/地址"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
) -> dict:
    """外景采集页的建筑选择器数据（不返回几何，保持轻量）。"""
    query = db.query(Building.id, Building.code, Building.name, Building.address)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(Building.name.ilike(like), Building.code.ilike(like), Building.address.ilike(like))
        )
    rows = query.order_by(Building.id.desc()).limit(limit).all()
    return ok(
        [
            {"id": r.id, "code": r.code, "name": r.name, "address": r.address}
            for r in rows
        ]
    )


@router.get("")
def list_media(
    page: PageParams = Depends(),
    building_id: int | None = Query(None),
    kind: str | None = Query(None),
    facade: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
) -> dict:
    query = db.query(FacadeMedia)
    if building_id is not None:
        query = query.filter(FacadeMedia.building_id == building_id)
    if kind:
        query = query.filter(FacadeMedia.kind == _check_kind(kind))
    if facade:
        query = query.filter(FacadeMedia.facade == _check_facade(facade))
    if page.keyword:
        like = f"%{page.keyword.strip()}%"
        query = query.filter(
            or_(FacadeMedia.file_name.ilike(like), FacadeMedia.remark.ilike(like))
        )

    total = query.count()
    rows = (
        query.order_by(
            FacadeMedia.is_primary.desc(),
            FacadeMedia.taken_at.desc().nulls_last(),
            FacadeMedia.id.desc(),
        )
        .offset(page.offset)
        .limit(page.page_size)
        .all()
    )
    return page_ok([_out(m) for m in rows], total, page.page, page.page_size)


@router.get("/stats")
def media_stats(
    building_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(guard_view),
) -> dict:
    query = db.query(FacadeMedia.facade, FacadeMedia.kind, func.count(FacadeMedia.id))
    if building_id is not None:
        query = query.filter(FacadeMedia.building_id == building_id)
    rows = query.group_by(FacadeMedia.facade, FacadeMedia.kind).all()

    by_facade = {key: 0 for key in FACADE_DIRECTIONS}
    by_kind = {key: 0 for key in FACADE_KINDS}
    total = 0
    for facade, kind, count in rows:
        total += count
        by_facade[facade] = by_facade.get(facade, 0) + count
        by_kind[kind] = by_kind.get(kind, 0) + count

    cover = None
    if building_id is not None:
        primary = (
            db.query(FacadeMedia)
            .filter(FacadeMedia.building_id == building_id)
            .order_by(FacadeMedia.is_primary.desc(), FacadeMedia.id.desc())
            .first()
        )
        if primary:
            cover = media_svc.file_url(primary.thumb_path) or media_svc.file_url(primary.file_path)

    return ok(
        {
            "total": total,
            "by_facade": by_facade,
            "by_kind": by_kind,
            "cover_url": cover,
        }
    )


@router.post("/upload")
def upload_media(
    request: Request,
    building_id: int = Form(..., description="所属建筑物"),
    kind: str = Form("photo", description="photo/panorama/model"),
    facade: str = Form("other", description="east/south/west/north/top/other"),
    floor_no: int | None = Form(None),
    taken_at: str | None = Form(None),
    remark: str | None = Form(None),
    lng: float | None = Form(None),
    lat: float | None = Form(None),
    files: list[UploadFile] = File(..., description="影像文件，可多选"),
    db: Session = Depends(get_db),
    user: User = Depends(guard_create),
) -> dict:
    """批量上传同一立面/楼层的影像，元数据统一应用到本批文件。"""
    _check_kind(kind)
    _check_facade(facade)
    building = db.get(Building, building_id)
    if building is None:
        raise NotFound("建筑物不存在")
    if not files:
        raise AppError("请选择要上传的文件")

    form_taken_at = _parse_dt(taken_at)
    created: list[FacadeMedia] = []
    for upload in files:
        info = media_svc.save_upload(upload, building_id, kind)
        media = FacadeMedia(
            building_id=building_id,
            kind=kind,
            facade=facade,
            floor_no=floor_no,
            file_name=info["file_name"],
            file_path=info["file_path"],
            thumb_path=info.get("thumb_path"),
            mime=info.get("mime"),
            file_size=info.get("file_size") or 0,
            width=info.get("width"),
            height=info.get("height"),
            # 表单填写的优先，其次用 EXIF 拍摄时间/GPS
            taken_at=form_taken_at or info.get("taken_at"),
            lng=lng if lng is not None else info.get("lng"),
            lat=lat if lat is not None else info.get("lat"),
            uploader_id=user.id,
            uploader_name=user.real_name or user.username,
            remark=remark,
            extra=info.get("extra"),
        )
        db.add(media)
        created.append(media)

    db.flush()
    # 该建筑还没有封面时，首张照片自动作为封面
    if building_id is not None:
        has_primary = (
            db.query(FacadeMedia.id)
            .filter(FacadeMedia.building_id == building_id, FacadeMedia.is_primary.is_(True))
            .first()
        )
        if not has_primary:
            first_photo = next((m for m in created if m.kind != "model"), None)
            if first_photo is not None:
                first_photo.is_primary = True

    log_action(
        db,
        user,
        "create",
        f"facade:{building_id}",
        {"count": len(created), "kind": kind, "facade": facade},
        client_ip(request),
    )
    db.commit()
    for media in created:
        db.refresh(media)
    return ok([_out(m) for m in created])


@router.put("/{media_id}")
def update_media(
    media_id: int,
    payload: FacadeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(guard_update),
) -> dict:
    media = _get_media(db, media_id)
    data = payload.model_dump(exclude_unset=True)
    if "facade" in data and data["facade"]:
        data["facade"] = _check_facade(data["facade"])
    if "is_primary" in data and data["is_primary"]:
        db.query(FacadeMedia).filter(
            FacadeMedia.building_id == media.building_id,
            FacadeMedia.id != media.id,
        ).update({FacadeMedia.is_primary: False}, synchronize_session=False)
    for key, value in data.items():
        setattr(media, key, value)

    log_action(db, user, "update", f"facade:{media.id}", data, client_ip(request))
    db.commit()
    db.refresh(media)
    return ok(_out(media))


@router.delete("/{media_id}")
def delete_media(
    media_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(guard_delete),
) -> dict:
    media = _get_media(db, media_id)
    media_svc.delete_files(media.file_path, media.thumb_path)
    log_action(db, user, "delete", f"facade:{media.id}", {"file": media.file_name}, client_ip(request))
    db.delete(media)
    db.commit()
    return ok({"id": media_id})


@router.post("/batch-delete")
def batch_delete(
    payload: IdsPayload,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(guard_delete),
) -> dict:
    if not payload.ids:
        raise AppError("请选择要删除的影像")
    rows = db.query(FacadeMedia).filter(FacadeMedia.id.in_(payload.ids)).all()
    for media in rows:
        media_svc.delete_files(media.file_path, media.thumb_path)
        db.delete(media)
    log_action(db, user, "delete", "facade", {"count": len(rows)}, client_ip(request))
    db.commit()
    return ok({"count": len(rows)})
