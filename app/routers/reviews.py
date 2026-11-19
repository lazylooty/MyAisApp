from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import AppSettings, EmployeeCard, Review, Role, User
from app.security import (
    SENIOR_ROLES,
    STAFF_ROLES,
    get_current_user,
    get_current_user_optional,
    require_roles,
)
from app.templating import build_context, templates
from app.utils import flash_redirect, parse_opt_int

router = APIRouter()


def _recalculate_employee_rating(db: Session, target_user_id: Optional[int]) -> None:
    if not target_user_id:
        return
    card = db.query(EmployeeCard).filter(EmployeeCard.id_user == target_user_id).first()
    if not card:
        return
    approved = (
        db.query(Review)
        .filter(Review.target_user_id == target_user_id, Review.is_approved.is_(True))
        .all()
    )
    if approved:
        avg = sum(r.rating for r in approved) / len(approved)
        card.rating = Decimal(f"{avg:.1f}")


@router.get("/reviews", response_class=HTMLResponse)
def reviews_page(
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    is_senior = bool(user and user.role and user.role.name in SENIOR_ROLES)

    query = db.query(Review).options(joinedload(Review.author), joinedload(Review.target))
    if not is_senior:
        if user:
            query = query.filter(
                (Review.is_approved.is_(True)) | (Review.author_user_id == user.id_user)
            )
        else:
            query = query.filter(Review.is_approved.is_(True))

    reviews = query.order_by(Review.created_date.desc()).all()
    staff_users = (
        db.query(User)
        .join(Role)
        .filter(Role.name.in_(STAFF_ROLES), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="reviews.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="reviews",
            reviews=reviews,
            staff_users=staff_users,
        ),
    )


@router.post("/reviews/create")
def create_review(
    review_text: str = Form(...),
    rating: int = Form(...),
    target_user_id: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    clean_text = review_text.strip()
    if not clean_text or rating < 1 or rating > 5:
        return flash_redirect("/reviews", error="Введите текст отзыва и выберите оценку от 1 до 5.")

    target_id = parse_opt_int(target_user_id)
    if target_id is not None:
        exists_target = db.query(User.id_user).filter(User.id_user == target_id).first()
        if not exists_target:
            target_id = None

    agency = db.query(AppSettings).first()
    require_mod = agency.reviews_require_moderation if agency else True
    is_senior = bool(user.role and user.role.name in SENIOR_ROLES)
    auto_approve = (not require_mod) or is_senior

    review = Review(
        author_user_id=user.id_user,
        target_user_id=target_id,
        review_text=clean_text[:2000],
        rating=rating,
        is_approved=auto_approve,
    )
    db.add(review)
    db.flush()

    if auto_approve:
        _recalculate_employee_rating(db, target_id)
    db.commit()

    if auto_approve:
        return flash_redirect("/reviews", message="Спасибо! Ваш отзыв опубликован.")
    return flash_redirect(
        "/reviews",
        message="Спасибо! Отзыв отправлен на модерацию и появится после проверки.",
    )


@router.post("/reviews/{review_id}/toggle")
def toggle_review_approval(
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(SENIOR_ROLES)),
):
    review = db.query(Review).filter(Review.id_review == review_id).first()
    if not review:
        return flash_redirect("/reviews", error="Отзыв не найден.")

    review.is_approved = not review.is_approved
    db.flush()
    _recalculate_employee_rating(db, review.target_user_id)
    db.commit()
    return flash_redirect("/reviews", message="Статус публикации отзыва обновлен.")


@router.post("/reviews/{review_id}/delete")
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(SENIOR_ROLES)),
):
    review = db.query(Review).filter(Review.id_review == review_id).first()
    if not review:
        return flash_redirect("/reviews", error="Отзыв не найден.")

    target_id = review.target_user_id
    db.delete(review)
    db.flush()
    _recalculate_employee_rating(db, target_id)
    db.commit()
    return flash_redirect("/reviews", message="Отзыв удален.")
