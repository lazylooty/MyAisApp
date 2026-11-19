from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    BuildingType,
    Client,
    District,
    Property,
    PropertyCategory,
    PropertyStatus,
    RepairType,
    User,
)
from app.security import ROLE_CLIENT, SENIOR_ROLES, STAFF_ROLES, get_current_user, require_roles
from app.templating import build_context, templates
from app.utils import flash_redirect, parse_opt_int, parse_opt_positive_float

router = APIRouter()


@router.get("/properties", response_class=HTMLResponse)
def properties_workspace(
    request: Request,
    district_id: Optional[str] = None,
    category_id: Optional[str] = None,
    max_price: Optional[str] = None,
    min_area: Optional[str] = None,
    rooms: Optional[str] = None,
    match_client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = user.role.name if user.role else ROLE_CLIENT
    is_staff = role_name in STAFF_ROLES

    d_id = parse_opt_int(district_id)
    c_id = parse_opt_int(category_id)
    r_cnt = parse_opt_int(rooms)
    m_price = parse_opt_positive_float(max_price)
    m_area = parse_opt_positive_float(min_area)
    mc_id = parse_opt_int(match_client_id) if is_staff else None

    matched_client = None
    if mc_id and is_staff:
        matched_client = (
            db.query(Client)
            .options(joinedload(Client.user), joinedload(Client.preferred_district))
            .filter(Client.id_client == mc_id)
            .first()
        )
        if matched_client:
            if not d_id and matched_client.id_preferred_district:
                d_id = matched_client.id_preferred_district
            if not m_price and matched_client.preferred_budget_max:
                m_price = float(matched_client.preferred_budget_max)

    query = db.query(Property).options(
        joinedload(Property.district),
        joinedload(Property.category),
        joinedload(Property.building_type),
        joinedload(Property.repair_type),
        joinedload(Property.status),
    )
    if d_id:
        query = query.filter(Property.id_district == d_id)
    if c_id:
        query = query.filter(Property.id_property_type == c_id)
    if r_cnt:
        query = query.filter(Property.rooms_count == r_cnt)
    if m_price:
        query = query.filter(Property.price <= m_price)
    if m_area:
        query = query.filter(Property.total_area >= m_area)

    items = query.order_by(Property.id_property.desc()).all()

    analytics_rows = []
    clients = []
    if is_staff:
        analytics_rows = (
            db.query(
                District.name.label("district_name"),
                func.count(Property.id_property).label("count"),
                func.avg(Property.price).label("avg_price"),
                func.avg(Property.price / func.nullif(Property.total_area, 0)).label("avg_sqm"),
            )
            .join(Property, Property.id_district == District.id_district)
            .group_by(District.name)
            .order_by(District.name.asc())
            .all()
        )
        clients = (
            db.query(Client)
            .join(User)
            .options(joinedload(Client.user))
            .order_by(User.full_name.asc())
            .all()
        )

    districts = db.query(District).order_by(District.name.asc()).all()
    categories = db.query(PropertyCategory).order_by(PropertyCategory.name.asc()).all()
    building_types = db.query(BuildingType).order_by(BuildingType.name.asc()).all()
    repair_types = db.query(RepairType).order_by(RepairType.name.asc()).all()
    statuses = db.query(PropertyStatus).order_by(PropertyStatus.id_status.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="properties.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="properties",
            properties=items,
            analytics_rows=analytics_rows,
            districts=districts,
            categories=categories,
            building_types=building_types,
            repair_types=repair_types,
            statuses=statuses,
            clients=clients,
            matched_client=matched_client,
            filters={
                "district_id": d_id,
                "category_id": c_id,
                "max_price": int(m_price) if m_price and m_price.is_integer() else (m_price or ""),
                "min_area": m_area or "",
                "rooms": r_cnt,
                "match_client_id": mc_id,
            },
        ),
    )


@router.post("/properties/create")
def create_property(
    cadastral_number: str = Form(...),
    address: str = Form(...),
    district_id: int = Form(...),
    total_area: float = Form(...),
    rooms_count: int = Form(...),
    floor: int = Form(...),
    building_type_id: int = Form(...),
    repair_type_id: int = Form(...),
    category_id: int = Form(...),
    status_id: int = Form(...),
    price: float = Form(...),
    location_rating: float = Form(8.5),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(STAFF_ROLES)),
):
    clean_cad = cadastral_number.strip()
    clean_addr = address.strip()
    if not clean_cad or not clean_addr:
        return flash_redirect("/properties", error="Укажите кадастровый номер и адрес объекта.")

    if total_area <= 0 or price <= 0 or rooms_count <= 0 or floor <= 0:
        return flash_redirect(
            "/properties",
            error="Площадь, цена, этаж и количество комнат должны быть положительными.",
        )

    if db.query(Property).filter(Property.cadastral_number == clean_cad).first():
        return flash_redirect(
            "/properties",
            error=f"Объект с кадастровым номером {clean_cad} уже существует.",
        )

    prop = Property(
        cadastral_number=clean_cad[:30],
        address=clean_addr[:255],
        id_district=district_id,
        total_area=Decimal(str(round(total_area, 2))),
        rooms_count=rooms_count,
        floor=floor,
        id_building_type=building_type_id,
        id_repair_type=repair_type_id,
        id_property_type=category_id,
        id_status=status_id,
        price=Decimal(str(round(price, 2))),
        location_rating=Decimal(str(round(min(max(location_rating, 0.0), 10.0), 1))),
        description=description.strip() or None,
    )
    try:
        db.add(prop)
        db.commit()
    except IntegrityError:
        db.rollback()
        return flash_redirect(
            "/properties",
            error="Ошибка сохранения: проверьте уникальность кадастрового номера и справочники.",
        )

    sqm = price / total_area
    return flash_redirect(
        "/properties",
        message=f"Объект добавлен. Расчетная стоимость за м²: {sqm:,.0f} ₽.".replace(",", " "),
    )


@router.post("/properties/{property_id}/status")
def update_property_status(
    property_id: int,
    status_id: int = Form(...),
    price: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(SENIOR_ROLES)),
):
    prop = db.query(Property).filter(Property.id_property == property_id).first()
    if not prop:
        return flash_redirect("/properties", error="Объект не найден.")

    status_exists = db.query(PropertyStatus.id_status).filter(PropertyStatus.id_status == status_id).first()
    if not status_exists:
        return flash_redirect("/properties", error="Выбран несуществующий статус объекта.")

    prop.id_status = status_id
    parsed_price = parse_opt_positive_float(price)
    if parsed_price is not None:
        prop.price = Decimal(str(round(parsed_price, 2)))

    db.commit()
    return flash_redirect("/properties", message="Данные объекта обновлены.")


@router.post("/properties/{property_id}/delete")
def delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(SENIOR_ROLES)),
):
    prop = db.query(Property).filter(Property.id_property == property_id).first()
    if not prop:
        return flash_redirect("/properties", error="Объект не найден.")

    try:
        db.delete(prop)
        db.commit()
    except Exception:
        db.rollback()
        return flash_redirect(
            "/properties",
            error="Нельзя удалить объект, так как к нему привязаны сделки, показы или договоры.",
        )

    return flash_redirect("/properties", message="Объект недвижимости удален.")
