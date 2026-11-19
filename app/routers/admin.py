from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import AppSettings, Client, Role, User
from app.security import ROLE_ADMIN, ROLE_CLIENT, hash_password, require_roles
from app.templating import build_context, templates
from app.utils import flash_redirect

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
def admin_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([ROLE_ADMIN])),
):
    users = (
        db.query(User)
        .options(joinedload(User.role))
        .order_by(User.id_user.asc())
        .all()
    )
    roles = db.query(Role).order_by(Role.id_role.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="admin",
            users=users,
            roles=roles,
        ),
    )


@router.post("/admin/users/create")
def admin_create_user(
    login: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    inn: str = Form(""),
    role_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([ROLE_ADMIN])),
):
    clean_login = login.strip()
    clean_name = full_name.strip()
    clean_phone = phone.strip()
    clean_email = email.strip()

    if not clean_login or not clean_name or not clean_phone or not clean_email:
        return flash_redirect("/admin", error="Заполните все обязательные поля пользователя.")

    if len(password) < 4:
        return flash_redirect("/admin", error="Пароль должен содержать не менее 4 символов.")

    exists = (
        db.query(User)
        .filter(
            (User.login == clean_login)
            | (User.phone == clean_phone)
            | (User.email == clean_email)
        )
        .first()
    )
    if exists:
        return flash_redirect(
            "/admin",
            error="Пользователь с таким логином, телефоном или email уже существует.",
        )

    role = db.query(Role).filter(Role.id_role == role_id).first()
    if not role:
        return flash_redirect("/admin", error="Выбрана несуществующая роль.")

    new_user = User(
        id_role=role_id,
        login=clean_login[:50],
        password_hash=hash_password(password),
        full_name=clean_name[:150],
        phone=clean_phone[:20],
        email=clean_email[:100],
        inn=inn.strip()[:12] or None,
        is_active=True,
    )
    try:
        db.add(new_user)
        db.flush()
        if role.name == ROLE_CLIENT:
            db.add(Client(id_user=new_user.id_user))
        db.commit()
    except IntegrityError:
        db.rollback()
        return flash_redirect("/admin", error="Ошибка создания пользователя: дубликат контактов.")

    return flash_redirect("/admin", message=f"Пользователь «{new_user.full_name}» создан.")


@router.post("/admin/users/{target_user_id}/update")
def admin_update_user(
    target_user_id: int,
    role_id: int = Form(...),
    is_active: str = Form("0"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([ROLE_ADMIN])),
):
    target = (
        db.query(User)
        .options(joinedload(User.client_profile), joinedload(User.role))
        .filter(User.id_user == target_user_id)
        .first()
    )
    if not target:
        return flash_redirect("/admin", error="Пользователь не найден.")

    role = db.query(Role).filter(Role.id_role == role_id).first()
    if not role:
        return flash_redirect("/admin", error="Указанная роль не найдена.")

    active_bool = is_active == "1"
    if target.id_user == user.id_user and not active_bool:
        return flash_redirect(
            "/admin",
            error="Нельзя заблокировать собственную учетную запись администратора.",
        )
    if target.id_user == user.id_user and role.name != ROLE_ADMIN:
        return flash_redirect(
            "/admin",
            error="Нельзя снять роль Администратора со своей текущей учетной записи.",
        )

    target.id_role = role_id
    target.is_active = active_bool

    if role.name == ROLE_CLIENT and not target.client_profile:
        db.add(Client(id_user=target.id_user))

    db.commit()
    return flash_redirect("/admin", message=f"Права и статус пользователя «{target.full_name}» обновлены.")


@router.post("/admin/settings")
def admin_update_settings(
    agency_name: str = Form(...),
    hero_title: str = Form(...),
    hero_subtitle: str = Form(...),
    about_text: str = Form(...),
    stat_years: str = Form(...),
    stat_deals: str = Form(...),
    stat_clients: str = Form(...),
    stat_satisfaction: str = Form(...),
    agency_inn: str = Form(...),
    agency_phone: str = Form(...),
    agency_email: str = Form(...),
    agency_address: str = Form(...),
    reviews_require_moderation: str = Form("0"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles([ROLE_ADMIN])),
):
    required_vals = [
        agency_name.strip(),
        hero_title.strip(),
        hero_subtitle.strip(),
        about_text.strip(),
        stat_years.strip(),
        stat_deals.strip(),
        stat_clients.strip(),
        stat_satisfaction.strip(),
        agency_inn.strip(),
        agency_phone.strip(),
        agency_email.strip(),
        agency_address.strip(),
    ]
    if any(not v for v in required_vals):
        return flash_redirect("/admin", error="Все текстовые поля настроек должны быть заполнены.")

    app_settings = db.query(AppSettings).first()
    if not app_settings:
        app_settings = AppSettings()
        db.add(app_settings)

    app_settings.agency_name = agency_name.strip()[:255]
    app_settings.hero_title = hero_title.strip()[:255]
    app_settings.hero_subtitle = hero_subtitle.strip()
    app_settings.about_text = about_text.strip()
    app_settings.stat_years = stat_years.strip()[:40]
    app_settings.stat_deals = stat_deals.strip()[:40]
    app_settings.stat_clients = stat_clients.strip()[:40]
    app_settings.stat_satisfaction = stat_satisfaction.strip()[:40]
    app_settings.agency_inn = agency_inn.strip()[:20]
    app_settings.agency_phone = agency_phone.strip()[:30]
    app_settings.agency_email = agency_email.strip()[:120]
    app_settings.agency_address = agency_address.strip()[:255]
    app_settings.reviews_require_moderation = reviews_require_moderation == "1"

    db.commit()
    return flash_redirect("/admin", message="Настройки приложения и данные страницы «О себе» сохранены.")
