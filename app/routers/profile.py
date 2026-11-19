from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import EmployeeCard, Notification, PassportData, Position, Role, User
from app.security import SENIOR_ROLES, STAFF_ROLES, get_current_user, require_roles
from app.templating import build_context, templates
from app.utils import flash_redirect

router = APIRouter()

ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


@router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notifications = (
        db.query(Notification)
        .filter(Notification.id_user == user.id_user)
        .order_by(Notification.send_datetime.desc())
        .limit(30)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="profile",
            notifications=notifications,
        ),
    )


@router.post("/profile/update")
def update_profile(
    full_name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    inn: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    clean_name = full_name.strip()
    clean_phone = phone.strip()
    clean_email = email.strip()
    if not clean_name or not clean_phone or not clean_email:
        return flash_redirect("/profile", error="ФИО, телефон и email не могут быть пустыми.")

    user.full_name = clean_name[:150]
    user.phone = clean_phone[:20]
    user.email = clean_email[:100]
    user.inn = inn.strip()[:12] or None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return flash_redirect("/profile", error="Телефон или email уже занят другим пользователем.")

    return flash_redirect("/profile", message="Данные профиля сохранены.")


@router.post("/profile/passport")
def update_passport(
    passport_series: str = Form(...),
    passport_number: str = Form(...),
    issue_date: str = Form(...),
    department_code: str = Form(...),
    issued_by: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    clean_series = passport_series.strip()
    clean_number = passport_number.strip()
    clean_code = department_code.strip()
    clean_issued = issued_by.strip()
    if not clean_series or not clean_number or not clean_code or not clean_issued:
        return flash_redirect("/profile", error="Заполните все обязательные паспортные поля.")

    try:
        parsed_date = datetime.strptime(issue_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return flash_redirect("/profile", error="Укажите корректную дату выдачи паспорта.")

    passport = db.query(PassportData).filter(PassportData.id_user == user.id_user).first()
    if not passport:
        passport = PassportData(
            id_user=user.id_user,
            passport_series=clean_series[:4],
            passport_number=clean_number[:6],
            issue_date=parsed_date,
            department_code=clean_code[:7],
            issued_by=clean_issued[:255],
        )
        db.add(passport)
    else:
        passport.passport_series = clean_series[:4]
        passport.passport_number = clean_number[:6]
        passport.issue_date = parsed_date
        passport.department_code = clean_code[:7]
        passport.issued_by = clean_issued[:255]

    db.commit()
    return flash_redirect(
        "/profile",
        message="Паспортные данные сохранены (используются при автозаполнении договоров).",
    )


@router.post("/notifications/read-all")
def mark_notifications_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.id_user == user.id_user, Notification.is_read.is_(False)
    ).update({"is_read": True})
    db.commit()
    return flash_redirect("/profile", message="Все уведомления отмечены как прочитанные.")


# ---------------------------------------------------------------------------
# Управление визитками сотрудников (Use Case №13: Риэлтор и Администратор)
# ---------------------------------------------------------------------------


@router.get("/team", response_class=HTMLResponse)
def team_cards_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(SENIOR_ROLES)),
):
    cards = (
        db.query(EmployeeCard)
        .options(joinedload(EmployeeCard.user), joinedload(EmployeeCard.position))
        .order_by(EmployeeCard.id_card.asc())
        .all()
    )
    staff_users = (
        db.query(User)
        .join(Role)
        .filter(Role.name.in_(STAFF_ROLES), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )
    positions = db.query(Position).order_by(Position.name.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="team.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="team",
            cards=cards,
            staff_users=staff_users,
            positions=positions,
        ),
    )


@router.post("/team/save")
async def save_employee_card(
    user_id: int = Form(...),
    position_id: int = Form(...),
    experience_years: int = Form(0),
    description: str = Form(""),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(SENIOR_ROLES)),
):
    if experience_years < 0 or experience_years > 100:
        return flash_redirect("/team", error="Стаж работы должен быть от 0 до 100 лет.")

    target_user = db.query(User.id_user).filter(User.id_user == user_id).first()
    pos = db.query(Position.id_position).filter(Position.id_position == position_id).first()
    if not target_user or not pos:
        return flash_redirect("/team", error="Выбран несуществующий сотрудник или должность.")

    photo_rel_path: Optional[str] = None
    if photo and photo.filename:
        ext = Path(photo.filename).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTS:
            return flash_redirect("/team", error="Допустимы только изображения JPG, PNG или WEBP.")
        content = await photo.read()
        if len(content) > MAX_PHOTO_BYTES:
            return flash_redirect("/team", error="Размер фотографии не должен превышать 5 МБ.")
        filename = f"{uuid.uuid4().hex}{ext}"
        (settings.photos_dir / filename).write_bytes(content)
        photo_rel_path = f"/media/photos/{filename}"

    card = db.query(EmployeeCard).filter(EmployeeCard.id_user == user_id).first()
    if not card:
        card = EmployeeCard(
            id_user=user_id,
            id_position=position_id,
            experience_years=experience_years,
            description=description.strip()[:1000] or None,
            photo_path=photo_rel_path,
        )
        db.add(card)
    else:
        card.id_position = position_id
        card.experience_years = experience_years
        card.description = description.strip()[:1000] or None
        if photo_rel_path:
            card.photo_path = photo_rel_path

    db.commit()
    return flash_redirect(
        "/team",
        message="Визитка сотрудника сохранена и обновлена на странице «О себе».",
    )
