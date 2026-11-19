from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Client,
    ClientRole,
    Deal,
    DealParticipant,
    DealStatus,
    DealType,
    EscrowStatus,
    Notification,
    Property,
    Role,
    User,
)
from app.security import ROLE_CLIENT, SENIOR_ROLES, STAFF_ROLES, get_current_user, require_roles
from app.templating import build_context, templates
from app.utils import flash_redirect, parse_opt_int

router = APIRouter()


@router.get("/deals", response_class=HTMLResponse)
def deals_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role_name = user.role.name if user.role else ROLE_CLIENT
    is_staff = role_name in STAFF_ROLES

    query = db.query(Deal).options(
        joinedload(Deal.property_obj),
        joinedload(Deal.realtor),
        joinedload(Deal.deal_type),
        joinedload(Deal.deal_status),
        joinedload(Deal.escrow_status),
        joinedload(Deal.participants).joinedload(DealParticipant.client).joinedload(Client.user),
        joinedload(Deal.participants).joinedload(DealParticipant.client_role),
        joinedload(Deal.contracts),
    )

    if not is_staff:
        if user.client_profile:
            query = (
                query.join(DealParticipant)
                .filter(DealParticipant.id_client == user.client_profile.id_client)
                .distinct()
            )
        else:
            query = query.filter(Deal.id_deal == -1)

    deals = query.order_by(Deal.id_deal.desc()).all()

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
    deal_types = db.query(DealType).order_by(DealType.id_deal_type.asc()).all() if is_staff else []
    deal_statuses = db.query(DealStatus).order_by(DealStatus.id_deal_status.asc()).all() if is_staff else []
    escrow_statuses = (
        db.query(EscrowStatus).order_by(EscrowStatus.id_escrow_status.asc()).all()
        if is_staff
        else []
    )
    client_roles = db.query(ClientRole).order_by(ClientRole.id_client_role.asc()).all() if is_staff else []

    return templates.TemplateResponse(
        request=request,
        name="deals.html",
        context=build_context(
            request,
            db,
            user,
            active_nav="deals",
            deals=deals,
            properties=properties,
            clients=clients,
            realtors=realtors,
            deal_types=deal_types,
            deal_statuses=deal_statuses,
            escrow_statuses=escrow_statuses,
            client_roles=client_roles,
        ),
    )


@router.post("/deals/create")
def create_deal(
    property_id: int = Form(...),
    realtor_id: int = Form(...),
    deal_type_id: int = Form(...),
    deal_status_id: int = Form(...),
    escrow_status_id: int = Form(...),
    final_price: float = Form(...),
    commission_rate: float = Form(2.5),
    client_1_id: int = Form(...),
    client_1_role_id: int = Form(...),
    client_2_id: str = Form("0"),
    client_2_role_id: str = Form("0"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(STAFF_ROLES)),
):
    if final_price <= 0:
        return flash_redirect("/deals", error="Сумма сделки должна быть положительной.")

    prop = db.query(Property.id_property).filter(Property.id_property == property_id).first()
    realtor = db.query(User.id_user).filter(User.id_user == realtor_id, User.is_active.is_(True)).first()
    c1_obj = (
        db.query(Client)
        .options(joinedload(Client.user))
        .filter(Client.id_client == client_1_id)
        .first()
    )
    r1_obj = db.query(ClientRole.id_client_role).filter(ClientRole.id_client_role == client_1_role_id).first()
    if not prop or not realtor or not c1_obj or not r1_obj:
        return flash_redirect("/deals", error="Проверьте корректность выбранного объекта, риэлтора и клиента.")

    c2 = parse_opt_int(client_2_id)
    r2 = parse_opt_int(client_2_role_id)
    if c2 and c2 != client_1_id:
        c2_exists = db.query(Client.id_client).filter(Client.id_client == c2).first()
        r2_exists = (
            db.query(ClientRole.id_client_role).filter(ClientRole.id_client_role == r2).first()
            if r2
            else None
        )
        if not c2_exists or not r2_exists:
            return flash_redirect("/deals", error="Укажите корректную роль для второго участника сделки.")

    deal = Deal(
        id_property=property_id,
        responsible_realtor_id=realtor_id,
        id_deal_type=deal_type_id,
        id_deal_status=deal_status_id,
        id_escrow_status=escrow_status_id,
        final_price=Decimal(str(round(final_price, 2))),
        commission_rate=Decimal(str(round(min(max(commission_rate, 0.0), 100.0), 2))),
        start_date=date.today(),
    )
    try:
        db.add(deal)
        db.flush()

        db.add(
            DealParticipant(
                id_deal=deal.id_deal,
                id_client=client_1_id,
                id_client_role=client_1_role_id,
            )
        )
        if c2 and c2 != client_1_id and r2:
            db.add(
                DealParticipant(
                    id_deal=deal.id_deal,
                    id_client=c2,
                    id_client_role=r2,
                )
            )

        if c1_obj.user:
            db.add(
                Notification(
                    id_user=c1_obj.user.id_user,
                    message_text=f"Открыта новая сделка №{deal.id_deal} на сумму {final_price:,.0f} ₽.".replace(",", " "),
                )
            )

        db.commit()
    except IntegrityError:
        db.rollback()
        return flash_redirect("/deals", error="Ошибка создания сделки: проверьте выбранные справочники.")

    return flash_redirect("/deals", message=f"Сделка №{deal.id_deal} успешно создана.")


@router.post("/deals/{deal_id}/update")
def update_deal_status(
    deal_id: int,
    deal_status_id: int = Form(...),
    escrow_status_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(STAFF_ROLES)),
):
    deal = (
        db.query(Deal)
        .options(joinedload(Deal.participants).joinedload(DealParticipant.client))
        .filter(Deal.id_deal == deal_id)
        .first()
    )
    if not deal:
        return flash_redirect("/deals", error="Сделка не найдена.")

    done_status = db.query(DealStatus).filter(DealStatus.id_deal_status == deal_status_id).first()
    escrow_obj = db.query(EscrowStatus).filter(EscrowStatus.id_escrow_status == escrow_status_id).first()
    if not done_status or not escrow_obj:
        return flash_redirect("/deals", error="Выбран несуществующий статус сделки или эскроу.")

    deal.id_deal_status = deal_status_id
    deal.id_escrow_status = escrow_status_id
    if done_status.name == "Завершена":
        deal.end_date = date.today()

    for part in deal.participants:
        if part.client:
            db.add(
                Notification(
                    id_user=part.client.id_user,
                    message_text=f"Обновлен статус вашей сделки №{deal.id_deal}: {done_status.name}.",
                )
            )

    db.commit()
    return flash_redirect("/deals", message=f"Статус сделки №{deal_id} обновлен.")


@router.post("/deals/{deal_id}/delete")
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(SENIOR_ROLES)),
):
    deal = db.query(Deal).filter(Deal.id_deal == deal_id).first()
    if not deal:
        return flash_redirect("/deals", error="Сделка не найдена.")

    try:
        db.delete(deal)
        db.commit()
    except Exception:
        db.rollback()
        return flash_redirect("/deals", error="Не удалось удалить сделку из-за связанных записей.")

    return flash_redirect("/deals", message=f"Сделка №{deal_id} удалена.")
