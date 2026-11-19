from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    EmployeeCard,
    Inquiry,
    Notification,
    Property,
    PropertyCategory,
    District,
    Review,
    Role,
    User,
)
from app.security import ROLE_REALTOR, get_current_user_optional
from app.templating import build_context, templates
from app.utils import (
    flash_redirect,
    parse_opt_int,
    parse_opt_positive_float,
    safe_local_redirect,
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def about_page(
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    employees = (
        db.query(EmployeeCard)
        .options(joinedload(EmployeeCard.user), joinedload(EmployeeCard.position))
        .order_by(EmployeeCard.experience_years.desc())
        .all()
    )
    approved_reviews = (
        db.query(Review)
        .options(joinedload(Review.author), joinedload(Review.target))
        .filter(Review.is_approved.is_(True))
        .order_by(Review.created_date.desc())
        .limit(6)
        .all()
    )
    available_properties = (
        db.query(Property)
        .options(
            joinedload(Property.district),
            joinedload(Property.category),
            joinedload(Property.status),
        )
        .order_by(Property.id_property.desc())
        .limit(3)
        .all()
    )
    categories = db.query(PropertyCategory).order_by(PropertyCategory.id_property_type.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="about",
            employees=employees,
            reviews=approved_reviews,
            featured_properties=available_properties,
            categories=categories,
        ),
    )


@router.get("/catalog", response_class=HTMLResponse)
def public_catalog_page(
    request: Request,
    district_id: Optional[str] = None,
    category_id: Optional[str] = None,
    max_price: Optional[str] = None,
    rooms: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    query = db.query(Property).options(
        joinedload(Property.district),
        joinedload(Property.category),
        joinedload(Property.building_type),
        joinedload(Property.repair_type),
        joinedload(Property.status),
    )

    d_id = parse_opt_int(district_id)
    c_id = parse_opt_int(category_id)
    m_price = parse_opt_positive_float(max_price)
    r_cnt = parse_opt_int(rooms)

    if d_id:
        query = query.filter(Property.id_district == d_id)
    if c_id:
        query = query.filter(Property.id_property_type == c_id)
    if m_price:
        query = query.filter(Property.price <= m_price)
    if r_cnt:
        query = query.filter(Property.rooms_count == r_cnt)

    items = query.order_by(Property.id_property.desc()).all()
    districts = db.query(District).order_by(District.name.asc()).all()
    categories = db.query(PropertyCategory).order_by(PropertyCategory.name.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="catalog",
            properties=items,
            districts=districts,
            categories=categories,
            filters={
                "district_id": d_id,
                "category_id": c_id,
                "max_price": int(m_price) if m_price and m_price.is_integer() else (m_price or ""),
                "rooms": r_cnt,
            },
        ),
    )


@router.post("/inquiries/submit")
def submit_public_inquiry(
    full_name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(""),
    inquiry_type: str = Form("Консультация и запись"),
    property_id: str = Form(""),
    message: str = Form(""),
    redirect_to: str = Form("/"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    target_url = safe_local_redirect(redirect_to, default="/")
    clean_name = full_name.strip()
    clean_phone = phone.strip()
    if not clean_name or not clean_phone:
        return flash_redirect(
            target_url,
            error="Пожалуйста, укажите имя и контактный телефон.",
        )

    prop_id_int = parse_opt_int(property_id)
    if prop_id_int is not None:
        exists_prop = db.query(Property.id_property).filter(Property.id_property == prop_id_int).first()
        if not exists_prop:
            prop_id_int = None

    realtor = (
        db.query(User)
        .join(Role)
        .filter(Role.name == ROLE_REALTOR, User.is_active.is_(True))
        .first()
    )

    clean_type = inquiry_type.strip() or "Консультация"
    inquiry = Inquiry(
        id_user=user.id_user if user else None,
        id_property=prop_id_int,
        full_name=clean_name[:150],
        phone=clean_phone[:30],
        email=email.strip()[:120] or None,
        inquiry_type=clean_type[:80],
        message=message.strip() or None,
        status="Новое",
        assigned_realtor_id=realtor.id_user if realtor else None,
    )
    db.add(inquiry)

    if realtor:
        db.add(
            Notification(
                id_user=realtor.id_user,
                message_text=f"Новое обращение от {clean_name} ({clean_phone}): {clean_type}"[:500],
            )
        )

    db.commit()

    return flash_redirect(
        target_url,
        message="Ваше обращение принято! Риэлтор свяжется с вами в ближайшее время.",
    )
