from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Client,
    ClientTier,
    District,
    Inquiry,
    LeadSource,
    Notification,
    PassportData,
    Property,
    PropertyShowing,
    Role,
    ShowingStatus,
    User,
)
from app.security import (
    ROLE_CLIENT,
    STAFF_ROLES,
    get_current_user,
    hash_password,
    require_roles,
)
from app.templating import build_context, templates
from app.utils import flash_redirect, parse_opt_decimal, parse_opt_int

router = APIRouter()

ALLOWED_INQUIRY_STATUSES = {"Новое", "В работе", "Назначен показ", "Закрыто"}


# ---------------------------------------------------------------------------
# Обращения (Заявки)
# ---------------------------------------------------------------------------


@router.get("/inquiries", response_class=HTMLResponse)
def inquiries_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = user.role.name if user.role else ROLE_CLIENT
    is_staff = role_name in STAFF_ROLES

    query = db.query(Inquiry).options(
        joinedload(Inquiry.property_obj),
        joinedload(Inquiry.assigned_realtor),
        joinedload(Inquiry.user),
    )
    if not is_staff:
        query = query.filter(Inquiry.id_user == user.id_user)

    items = query.order_by(Inquiry.created_at.desc()).all()
    properties = db.query(Property).order_by(Property.address.asc()).all()
    realtors = (
        db.query(User)
        .join(Role)
        .filter(Role.name.in_(STAFF_ROLES), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
        if is_staff
        else []
    )

    return templates.TemplateResponse(
        request=request,
        name="inquiries.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="inquiries",
            inquiries=items,
            properties=properties,
            realtors=realtors,
        ),
    )


@router.post("/inquiries/{inquiry_id}/status")
def update_inquiry_status(
    inquiry_id: int,
    status: str = Form(...),
    assigned_realtor_id: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(STAFF_ROLES)),
):
    inquiry = db.query(Inquiry).filter(Inquiry.id_inquiry == inquiry_id).first()
    if not inquiry:
        return flash_redirect("/inquiries", error="Обращение не найдено.")

    clean_status = status.strip()
    if clean_status not in ALLOWED_INQUIRY_STATUSES:
        return flash_redirect("/inquiries", error="Указан недопустимый статус обращения.")

    inquiry.status = clean_status
    realtor_id = parse_opt_int(assigned_realtor_id)
    if realtor_id is not None:
        realtor = db.query(User.id_user).filter(User.id_user == realtor_id, User.is_active.is_(True)).first()
        if realtor:
            inquiry.assigned_realtor_id = realtor_id
    else:
        inquiry.assigned_realtor_id = None

    db.commit()
    return flash_redirect("/inquiries", message="Статус обращения обновлен.")


# ---------------------------------------------------------------------------
# База клиентов (Use Case №10 из курсового)
# ---------------------------------------------------------------------------


@router.get("/clients", response_class=HTMLResponse)
def clients_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(STAFF_ROLES)),
):
    clients = (
        db.query(Client)
        .join(User)
        .options(
            joinedload(Client.user).joinedload(User.passport),
            joinedload(Client.lead_source),
            joinedload(Client.client_tier),
            joinedload(Client.preferred_district),
        )
        .order_by(User.full_name.asc())
        .all()
    )
    lead_sources = db.query(LeadSource).order_by(LeadSource.name.asc()).all()
    client_tiers = db.query(ClientTier).order_by(ClientTier.name.asc()).all()
    districts = db.query(District).order_by(District.name.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="clients",
            clients=clients,
            lead_sources=lead_sources,
            client_tiers=client_tiers,
            districts=districts,
        ),
    )


@router.post("/clients/create")
def create_client(
    full_name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    login: str = Form(...),
    inn: str = Form(""),
    lead_source_id: str = Form(""),
    client_tier_id: str = Form(""),
    preferred_district_id: str = Form(""),
    preferred_budget_max: str = Form(""),
    notes: str = Form(""),
    passport_series: str = Form(""),
    passport_number: str = Form(""),
    issue_date: str = Form(""),
    department_code: str = Form(""),
    issued_by: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(STAFF_ROLES)),
):
    clean_name = full_name.strip()
    clean_login = login.strip()
    clean_phone = phone.strip()
    clean_email = email.strip()

    if not clean_name or not clean_login or not clean_phone or not clean_email:
        return flash_redirect("/clients", error="Заполните обязательные поля: ФИО, логин, телефон и email.")

    duplicate = (
        db.query(User)
        .filter(
            (User.login == clean_login)
            | (User.phone == clean_phone)
            | (User.email == clean_email)
        )
        .first()
    )
    if duplicate:
        return flash_redirect(
            "/clients",
            error="Дублирование данных: клиент с таким логином, телефоном или email уже существует.",
        )

    client_role = db.query(Role).filter(Role.name == ROLE_CLIENT).first()
    if not client_role:
        client_role = Role(name=ROLE_CLIENT)
        db.add(client_role)
        db.flush()

    new_user = User(
        id_role=client_role.id_role,
        login=clean_login[:50],
        password_hash=hash_password("client123"),
        full_name=clean_name[:150],
        phone=clean_phone[:20],
        email=clean_email[:100],
        inn=inn.strip()[:12] or None,
        is_active=True,
    )

    try:
        db.add(new_user)
        db.flush()

        p_series = passport_series.strip()
        p_number = passport_number.strip()
        p_issued = issued_by.strip()
        if p_series and p_number and p_issued:
            try:
                parsed_date = datetime.strptime(issue_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                parsed_date = datetime.today().date()
            db.add(
                PassportData(
                    id_user=new_user.id_user,
                    passport_series=p_series[:4],
                    passport_number=p_number[:6],
                    issue_date=parsed_date,
                    department_code=department_code.strip()[:7] or "000-000",
                    issued_by=p_issued[:255],
                )
            )

        db.add(
            Client(
                id_user=new_user.id_user,
                id_lead_source=parse_opt_int(lead_source_id),
                id_client_tier=parse_opt_int(client_tier_id),
                id_preferred_district=parse_opt_int(preferred_district_id),
                preferred_budget_max=parse_opt_decimal(preferred_budget_max),
                notes=notes.strip() or None,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return flash_redirect(
            "/clients",
            error="Не удалось сохранить клиента: проверьте уникальность данных и справочники.",
        )

    return flash_redirect(
        "/clients",
        message=f"Клиент «{new_user.full_name}» зарегистрирован (пароль по умолчанию: client123).",
    )


# ---------------------------------------------------------------------------
# График показов и календарь (Use Case №5 и №11 из курсового)
# ---------------------------------------------------------------------------


@router.get("/showings", response_class=HTMLResponse)
def showings_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = user.role.name if user.role else ROLE_CLIENT
    is_staff = role_name in STAFF_ROLES

    query = db.query(PropertyShowing).options(
        joinedload(PropertyShowing.property_obj),
        joinedload(PropertyShowing.client).joinedload(Client.user),
        joinedload(PropertyShowing.realtor),
        joinedload(PropertyShowing.showing_status),
    )
    if not is_staff:
        if user.client_profile:
            query = query.filter(PropertyShowing.id_client == user.client_profile.id_client)
        else:
            query = query.filter(PropertyShowing.id_showing == -1)

    showings = query.order_by(PropertyShowing.showing_datetime.desc()).all()
    properties = db.query(Property).order_by(Property.address.asc()).all() if is_staff else []
    clients = (
        db.query(Client)
        .join(User)
        .options(joinedload(Client.user))
        .order_by(User.full_name.asc())
        .all()
        if is_staff
        else []
    )
    realtors = (
        db.query(User)
        .join(Role)
        .filter(Role.name.in_(STAFF_ROLES), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
        if is_staff
        else []
    )
    showing_statuses = (
        db.query(ShowingStatus).order_by(ShowingStatus.id_showing_status.asc()).all()
        if is_staff
        else []
    )

    return templates.TemplateResponse(
        request=request,
        name="showings.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="showings",
            showings=showings,
            properties=properties,
            clients=clients,
            realtors=realtors,
            showing_statuses=showing_statuses,
        ),
    )


@router.post("/showings/create")
def create_showing(
    property_id: int = Form(...),
    client_id: int = Form(...),
    realtor_id: int = Form(...),
    showing_datetime: str = Form(...),
    result_comment: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(STAFF_ROLES)),
):
    try:
        dt = datetime.fromisoformat(showing_datetime.strip())
    except ValueError:
        return flash_redirect("/showings", error="Некорректный формат даты и времени показа.")

    prop_obj = db.query(Property).filter(Property.id_property == property_id).first()
    client_obj = (
        db.query(Client)
        .options(joinedload(Client.user))
        .filter(Client.id_client == client_id)
        .first()
    )
    realtor_obj = db.query(User).filter(User.id_user == realtor_id, User.is_active.is_(True)).first()
    if not prop_obj or not client_obj or not realtor_obj:
        return flash_redirect("/showings", error="Выбран несуществующий объект, клиент или специалист.")

    canceled = db.query(ShowingStatus).filter(ShowingStatus.name == "Отменен").first()
    window_start = dt - timedelta(minutes=45)
    window_end = dt + timedelta(minutes=45)

    conflict_q = db.query(PropertyShowing).filter(
        PropertyShowing.id_realtor == realtor_id,
        PropertyShowing.showing_datetime >= window_start,
        PropertyShowing.showing_datetime <= window_end,
    )
    if canceled:
        conflict_q = conflict_q.filter(
            PropertyShowing.id_showing_status != canceled.id_showing_status
        )
    if conflict_q.first():
        return flash_redirect(
            "/showings",
            error="Накладка в расписании: у выбранного сотрудника уже запланирован показ в это время (±45 мин).",
        )

    planned_status = db.query(ShowingStatus).filter(ShowingStatus.name == "Запланирован").first()
    if not planned_status:
        planned_status = db.query(ShowingStatus).first()
    if not planned_status:
        return flash_redirect("/showings", error="Справочник статусов показов не заполнен.")

    showing = PropertyShowing(
        id_property=property_id,
        id_client=client_id,
        id_realtor=realtor_id,
        id_showing_status=planned_status.id_showing_status,
        showing_datetime=dt,
        result_comment=result_comment.strip() or None,
    )
    db.add(showing)

    if client_obj.user:
        db.add(
            Notification(
                id_user=client_obj.user.id_user,
                message_text=(
                    f"Запланирован показ объекта ({prop_obj.address}) на "
                    f"{dt.strftime('%d.%m.%Y в %H:%M')}."
                )[:500],
            )
        )

    db.commit()
    return flash_redirect(
        "/showings",
        message="Показ запланирован, клиенту отправлено персональное уведомление.",
    )


@router.post("/showings/{showing_id}/status")
def update_showing_status(
    showing_id: int,
    showing_status_id: int = Form(...),
    result_comment: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(STAFF_ROLES)),
):
    showing = db.query(PropertyShowing).filter(PropertyShowing.id_showing == showing_id).first()
    if not showing:
        return flash_redirect("/showings", error="Запись показа не найдена.")

    status_obj = (
        db.query(ShowingStatus)
        .filter(ShowingStatus.id_showing_status == showing_status_id)
        .first()
    )
    if not status_obj:
        return flash_redirect("/showings", error="Указан несуществующий статус показа.")

    showing.id_showing_status = showing_status_id
    if result_comment.strip():
        showing.result_comment = result_comment.strip()
    db.commit()
    return flash_redirect("/showings", message="Статус показа обновлен.")
