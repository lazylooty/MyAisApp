from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Client, Role, User
from app.security import (
    COOKIE_NAME,
    ROLE_ADMIN,
    ROLE_CLIENT,
    create_access_token,
    get_current_user_optional,
    hash_password,
    verify_password,
)
from app.templating import build_context, templates
from app.utils import flash_redirect

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    if user:
        return RedirectResponse(url="/properties", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="auth_login.html",
        context=build_context(request, db, None, active_nav="login"),
    )


@router.post("/login")
def login_submit(
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    clean_login = login.strip()
    if not clean_login or not password:
        return flash_redirect("/login", error="Введите логин и пароль.")

    user = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.login == clean_login)
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return flash_redirect("/login", error="Неверный логин или пароль.")
    if not user.is_active:
        return flash_redirect("/login", error="Учетная запись заблокирована администратором.")

    token = create_access_token(user)
    target = "/admin" if user.role and user.role.name == ROLE_ADMIN else "/properties"
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    if user:
        return RedirectResponse(url="/properties", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="auth_register.html",
        context=build_context(request, db, None, active_nav="register"),
    )


@router.post("/register")
def register_submit(
    login: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    inn: str = Form(""),
    db: Session = Depends(get_db),
):
    clean_login = login.strip()
    clean_name = full_name.strip()
    clean_phone = phone.strip()
    clean_email = email.strip()

    if not clean_login or not clean_name or not clean_phone or not clean_email:
        return flash_redirect("/register", error="Заполните все обязательные поля.")

    if len(password) < 6:
        return flash_redirect("/register", error="Пароль должен содержать минимум 6 символов.")

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
            "/register",
            error="Пользователь с таким логином, телефоном или email уже существует.",
        )

    client_role = db.query(Role).filter(Role.name == ROLE_CLIENT).first()
    if not client_role:
        client_role = Role(name=ROLE_CLIENT)
        db.add(client_role)
        db.flush()

    new_user = User(
        id_role=client_role.id_role,
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
        db.add(Client(id_user=new_user.id_user))
        db.commit()
    except IntegrityError:
        db.rollback()
        return flash_redirect(
            "/register",
            error="Не удалось зарегистрироваться: логин, телефон или email уже заняты.",
        )

    db.refresh(new_user)
    new_user.role = client_role
    token = create_access_token(new_user)
    response = flash_redirect(
        "/profile",
        message="Регистрация прошла успешно! Добро пожаловать в личный кабинет.",
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@router.post("/logout")
@router.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
