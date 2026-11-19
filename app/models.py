from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Справочники (курсовой проект, таблицы 13–26)
# ---------------------------------------------------------------------------


class Role(Base):
    __tablename__ = "role"

    id_role: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    users: Mapped[List["User"]] = relationship("User", back_populates="role")


class Position(Base):
    __tablename__ = "position"

    id_position: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class District(Base):
    __tablename__ = "district"

    id_district: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class PropertyCategory(Base):
    __tablename__ = "property_category"

    id_property_type: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class BuildingType(Base):
    __tablename__ = "building_type"

    id_building_type: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class RepairType(Base):
    __tablename__ = "repair_type"

    id_repair_type: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class PropertyStatus(Base):
    __tablename__ = "property_status"

    id_status: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class LeadSource(Base):
    __tablename__ = "lead_source"

    id_lead_source: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class ClientTier(Base):
    __tablename__ = "client_tier"

    id_client_tier: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class DealType(Base):
    __tablename__ = "deal_type"

    id_deal_type: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class DealStatus(Base):
    __tablename__ = "deal_status"

    id_deal_status: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class EscrowStatus(Base):
    __tablename__ = "escrow_status"

    id_escrow_status: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class ClientRole(Base):
    __tablename__ = "client_role"

    id_client_role: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class ShowingStatus(Base):
    __tablename__ = "showing_status"

    id_showing_status: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


# ---------------------------------------------------------------------------
# Основные сущности (курсовой проект, таблицы 1–12 + обращения и настройки)
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id_user: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_role: Mapped[int] = mapped_column(ForeignKey("role.id_role"), nullable=False)
    login: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    passport: Mapped[Optional["PassportData"]] = relationship(
        "PassportData", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    client_profile: Mapped[Optional["Client"]] = relationship(
        "Client", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    employee_cards: Mapped[List["EmployeeCard"]] = relationship(
        "EmployeeCard", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )


class PassportData(Base):
    __tablename__ = "passport_data"

    id_passport: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        ForeignKey("users.id_user", ondelete="CASCADE"), unique=True, nullable=False
    )
    passport_series: Mapped[str] = mapped_column(String(4), nullable=False)
    passport_number: Mapped[str] = mapped_column(String(6), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    department_code: Mapped[str] = mapped_column(String(7), nullable=False)
    issued_by: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="passport")


class EmployeeCard(Base):
    __tablename__ = "employee_card"

    id_card: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        ForeignKey("users.id_user", ondelete="CASCADE"), nullable=False
    )
    id_position: Mapped[int] = mapped_column(ForeignKey("position.id_position"), nullable=False)
    photo_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    experience_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), default=Decimal("5.0"), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="employee_cards")
    position: Mapped["Position"] = relationship("Position")


class Review(Base):
    __tablename__ = "review"

    id_review: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id_user", ondelete="CASCADE"), nullable=False
    )
    target_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id_user", ondelete="SET NULL"), nullable=True
    )
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_date: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    author: Mapped["User"] = relationship("User", foreign_keys=[author_user_id])
    target: Mapped[Optional["User"]] = relationship("User", foreign_keys=[target_user_id])


class Notification(Base):
    __tablename__ = "notification"

    id_notification: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        ForeignKey("users.id_user", ondelete="CASCADE"), nullable=False
    )
    message_text: Mapped[str] = mapped_column(String(500), nullable=False)
    send_datetime: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="notifications")


class Property(Base):
    __tablename__ = "property"

    id_property: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cadastral_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    id_district: Mapped[int] = mapped_column(ForeignKey("district.id_district"), nullable=False)
    total_area: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    rooms_count: Mapped[int] = mapped_column(Integer, nullable=False)
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    id_building_type: Mapped[int] = mapped_column(
        ForeignKey("building_type.id_building_type"), nullable=False
    )
    id_repair_type: Mapped[int] = mapped_column(
        ForeignKey("repair_type.id_repair_type"), nullable=False
    )
    id_property_type: Mapped[int] = mapped_column(
        ForeignKey("property_category.id_property_type"), nullable=False
    )
    id_status: Mapped[int] = mapped_column(
        ForeignKey("property_status.id_status"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    location_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 1), default=Decimal("8.0"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    district: Mapped["District"] = relationship("District")
    building_type: Mapped["BuildingType"] = relationship("BuildingType")
    repair_type: Mapped["RepairType"] = relationship("RepairType")
    category: Mapped["PropertyCategory"] = relationship("PropertyCategory")
    status: Mapped["PropertyStatus"] = relationship("PropertyStatus")


class Client(Base):
    __tablename__ = "client"

    id_client: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        ForeignKey("users.id_user", ondelete="CASCADE"), unique=True, nullable=False
    )
    id_lead_source: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lead_source.id_lead_source"), nullable=True
    )
    id_client_tier: Mapped[Optional[int]] = mapped_column(
        ForeignKey("client_tier.id_client_tier"), nullable=True
    )
    preferred_budget_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    id_preferred_district: Mapped[Optional[int]] = mapped_column(
        ForeignKey("district.id_district"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="client_profile")
    lead_source: Mapped[Optional["LeadSource"]] = relationship("LeadSource")
    client_tier: Mapped[Optional["ClientTier"]] = relationship("ClientTier")
    preferred_district: Mapped[Optional["District"]] = relationship("District")


class Deal(Base):
    __tablename__ = "deal"

    id_deal: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_property: Mapped[int] = mapped_column(ForeignKey("property.id_property"), nullable=False)
    responsible_realtor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id_user"), nullable=False
    )
    id_deal_type: Mapped[int] = mapped_column(ForeignKey("deal_type.id_deal_type"), nullable=False)
    id_deal_status: Mapped[int] = mapped_column(
        ForeignKey("deal_status.id_deal_status"), nullable=False
    )
    id_escrow_status: Mapped[int] = mapped_column(
        ForeignKey("escrow_status.id_escrow_status"), nullable=False
    )
    final_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("3.00"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    property_obj: Mapped["Property"] = relationship("Property")
    realtor: Mapped["User"] = relationship("User", foreign_keys=[responsible_realtor_id])
    deal_type: Mapped["DealType"] = relationship("DealType")
    deal_status: Mapped["DealStatus"] = relationship("DealStatus")
    escrow_status: Mapped["EscrowStatus"] = relationship("EscrowStatus")
    participants: Mapped[List["DealParticipant"]] = relationship(
        "DealParticipant", back_populates="deal", cascade="all, delete-orphan"
    )
    contracts: Mapped[List["Contract"]] = relationship("Contract", back_populates="deal")


class DealParticipant(Base):
    __tablename__ = "deal_participant"

    id_participant: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_deal: Mapped[int] = mapped_column(
        ForeignKey("deal.id_deal", ondelete="CASCADE"), nullable=False
    )
    id_client: Mapped[int] = mapped_column(
        ForeignKey("client.id_client", ondelete="CASCADE"), nullable=False
    )
    id_client_role: Mapped[int] = mapped_column(
        ForeignKey("client_role.id_client_role"), nullable=False
    )

    deal: Mapped["Deal"] = relationship("Deal", back_populates="participants")
    client: Mapped["Client"] = relationship("Client")
    client_role: Mapped["ClientRole"] = relationship("ClientRole")


class ContractTemplate(Base):
    __tablename__ = "contract_template"

    id_template: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_date: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    contracts: Mapped[List["Contract"]] = relationship("Contract", back_populates="template")


class Contract(Base):
    __tablename__ = "contract"

    id_contract: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_deal: Mapped[Optional[int]] = mapped_column(
        ForeignKey("deal.id_deal", ondelete="SET NULL"), nullable=True
    )
    id_template: Mapped[int] = mapped_column(
        ForeignKey("contract_template.id_template"), nullable=False
    )
    id_property: Mapped[Optional[int]] = mapped_column(
        ForeignKey("property.id_property"), nullable=True
    )
    client_names: Mapped[str] = mapped_column(String(500), nullable=False)
    contract_number: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    generation_date: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    is_signed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    deal: Mapped[Optional["Deal"]] = relationship("Deal", back_populates="contracts")
    template: Mapped["ContractTemplate"] = relationship(
        "ContractTemplate", back_populates="contracts"
    )
    property_obj: Mapped[Optional["Property"]] = relationship("Property")


class PropertyShowing(Base):
    __tablename__ = "property_showing"

    id_showing: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_property: Mapped[int] = mapped_column(ForeignKey("property.id_property"), nullable=False)
    id_client: Mapped[int] = mapped_column(ForeignKey("client.id_client"), nullable=False)
    id_realtor: Mapped[int] = mapped_column(ForeignKey("users.id_user"), nullable=False)
    id_showing_status: Mapped[int] = mapped_column(
        ForeignKey("showing_status.id_showing_status"), nullable=False
    )
    showing_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    result_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    property_obj: Mapped["Property"] = relationship("Property")
    client: Mapped["Client"] = relationship("Client")
    realtor: Mapped["User"] = relationship("User", foreign_keys=[id_realtor])
    showing_status: Mapped["ShowingStatus"] = relationship("ShowingStatus")


class Inquiry(Base):
    """Обращения клиентов (заявки с модального окна на странице 'О себе' и со страницы 'Обращения')."""

    __tablename__ = "inquiry"

    id_inquiry: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id_user", ondelete="SET NULL"), nullable=True
    )
    id_property: Mapped[Optional[int]] = mapped_column(
        ForeignKey("property.id_property", ondelete="SET NULL"), nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    inquiry_type: Mapped[str] = mapped_column(String(80), default="Консультация", nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Новое", nullable=False)
    assigned_realtor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id_user", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[id_user])
    assigned_realtor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_realtor_id]
    )
    property_obj: Mapped[Optional["Property"]] = relationship("Property")


class AppSettings(Base):
    """Глобальные настройки приложения и статистика главной страницы (управляются Администратором)."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_name: Mapped[str] = mapped_column(
        String(255), default="ИП Голубина Ольга Геннадьевна", nullable=False
    )
    hero_title: Mapped[str] = mapped_column(
        String(255),
        default="Недвижимость с безупречной юридической чистотой",
        nullable=False,
    )
    hero_subtitle: Mapped[str] = mapped_column(
        Text,
        default=(
            "Персональное сопровождение сделок купли-продажи и аренды жилой и коммерческой "
            "недвижимости в Екатеринбурге. Проверка объектов, эскроу-расчеты и защита ваших интересов."
        ),
        nullable=False,
    )
    about_text: Mapped[str] = mapped_column(
        Text,
        default=(
            "ИП Голубина Ольга Геннадьевна — это бутиковый подход к каждой сделке. "
            "Мы не работаем на поток: каждый объект проходит глубокую правовую проверку ЕГРН, "
            "истории переходов права и обременений, а клиент получает прозрачный график показов, "
            "аналитику рыночной цены и готовый пакет юридических документов."
        ),
        nullable=False,
    )
    stat_years: Mapped[str] = mapped_column(String(40), default="12+ лет", nullable=False)
    stat_deals: Mapped[str] = mapped_column(String(40), default="640+", nullable=False)
    stat_clients: Mapped[str] = mapped_column(String(40), default="1 100+", nullable=False)
    stat_satisfaction: Mapped[str] = mapped_column(String(40), default="99%", nullable=False)
    agency_inn: Mapped[str] = mapped_column(String(20), default="667109876543", nullable=False)
    agency_phone: Mapped[str] = mapped_column(
        String(30), default="+7 (922) 123-45-67", nullable=False
    )
    agency_email: Mapped[str] = mapped_column(
        String(120), default="golubina.realty@example.ru", nullable=False
    )
    agency_address: Mapped[str] = mapped_column(
        String(255), default="г. Екатеринбург, ул. Малышева, д. 51", nullable=False
    )
    reviews_require_moderation: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
