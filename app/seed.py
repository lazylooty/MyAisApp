from datetime import date, datetime, timedelta
from decimal import Decimal
import json

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AppSettings,
    BuildingType,
    Client,
    ClientRole,
    ClientTier,
    ContractTemplate,
    Deal,
    DealParticipant,
    DealStatus,
    DealType,
    District,
    EmployeeCard,
    EscrowStatus,
    Inquiry,
    LeadSource,
    Notification,
    PassportData,
    Position,
    Property,
    PropertyCategory,
    PropertyShowing,
    PropertyStatus,
    RepairType,
    Review,
    Role,
    ShowingStatus,
    User,
)
from app.security import hash_password
from app.services.docx_service import create_sample_template_docx, extract_tags_from_docx


def _get_or_create(db: Session, model, **kwargs):
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    instance = model(**kwargs)
    db.add(instance)
    db.flush()
    return instance


def seed_initial_data(db: Session) -> None:
    """Начальное заполнение всех справочников, ролей, демо-пользователей, объектов, отзывов и шаблона."""
    # 1. Справочники
    roles = {
        name: _get_or_create(db, Role, name=name)
        for name in ["Гость", "Клиент", "Помощник риэлтора", "Риэлтор", "Администратор"]
    }
    positions = {
        name: _get_or_create(db, Position, name=name)
        for name in [
            "Руководитель / Ведущий риэлтор",
            "Риэлтор",
            "Помощник риэлтора",
            "Юрист по недвижимости",
        ]
    }
    districts = {
        name: _get_or_create(db, District, name=name)
        for name in ["Центр", "ВИЗ", "Ботаника", "Академический", "Уралмаш"]
    }
    categories = {
        name: _get_or_create(db, PropertyCategory, name=name)
        for name in ["Квартира", "Дом", "Апартаменты", "Коммерция"]
    }
    building_types = {
        name: _get_or_create(db, BuildingType, name=name)
        for name in ["Кирпичный", "Монолитный", "Панельный"]
    }
    repair_types = {
        name: _get_or_create(db, RepairType, name=name)
        for name in ["Дизайнерский", "Евроремонт", "Косметический", "Черновая отделка"]
    }
    prop_statuses = {
        name: _get_or_create(db, PropertyStatus, name=name)
        for name in ["Доступен", "Забронирован", "Продан"]
    }
    lead_sources = {
        name: _get_or_create(db, LeadSource, name=name)
        for name in ["Сайт (О себе)", "Рекомендация", "Авито / Циан", "Повторное обращение"]
    }
    client_tiers = {
        name: _get_or_create(db, ClientTier, name=name)
        for name in ["VIP", "Стандарт", "Инвестор"]
    }
    deal_types = {
        name: _get_or_create(db, DealType, name=name)
        for name in ["Купля-продажа", "Аренда"]
    }
    deal_statuses = {
        name: _get_or_create(db, DealStatus, name=name)
        for name in [
            "Первичная консультация",
            "Подготовка документов",
            "Регистрация в Росреестре",
            "Завершена",
            "Отменена",
        ]
    }
    escrow_statuses = {
        name: _get_or_create(db, EscrowStatus, name=name)
        for name in ["Не открыт", "Открыт", "Средства зачислены", "Средства раскрыты"]
    }
    client_roles = {
        name: _get_or_create(db, ClientRole, name=name)
        for name in ["Покупатель", "Продавец", "Арендатор", "Арендодатель"]
    }
    showing_statuses = {
        name: _get_or_create(db, ShowingStatus, name=name)
        for name in ["Запланирован", "Проведен", "Отменен"]
    }

    # 2. Настройки предприятия
    if db.query(AppSettings).count() == 0:
        db.add(
            AppSettings(
                agency_name=settings.agency_name,
                agency_inn="667109876543",
                agency_phone="+7 (922) 123-45-67",
                agency_email="golubina.realty@example.ru",
                agency_address="г. Екатеринбург, ул. Малышева, д. 51",
            )
        )

    # 3. Сотрудники и администратор
    admin_user = db.query(User).filter(User.login == "admin").first()
    if not admin_user:
        admin_user = User(
            id_role=roles["Администратор"].id_role,
            login="admin",
            password_hash=hash_password("admin123"),
            full_name="Администратор Системы",
            phone="+7 (900) 000-00-01",
            email="admin@golubina-realty.ru",
            inn="667100000001",
            is_active=True,
        )
        db.add(admin_user)
        db.flush()

    realtor_user = db.query(User).filter(User.login == "golubina").first()
    if not realtor_user:
        realtor_user = User(
            id_role=roles["Риэлтор"].id_role,
            login="golubina",
            password_hash=hash_password("realtor123"),
            full_name="Голубина Ольга Геннадьевна",
            phone="+7 (922) 123-45-67",
            email="golubina.realty@example.ru",
            inn="667109876543",
            is_active=True,
        )
        db.add(realtor_user)
        db.flush()

        db.add(
            EmployeeCard(
                id_user=realtor_user.id_user,
                id_position=positions["Руководитель / Ведущий риэлтор"].id_position,
                experience_years=12,
                description=(
                    "Частный практикующий риэлтор и эксперт по сделкам с недвижимостью. "
                    "Специализация: сложные цепочки купли-продажи, ипотечные и эскроу-сделки, "
                    "полная юридическая проверка объектов."
                ),
                rating=Decimal("5.0"),
            )
        )

    assistant_user = db.query(User).filter(User.login == "assistant").first()
    if not assistant_user:
        assistant_user = User(
            id_role=roles["Помощник риэлтора"].id_role,
            login="assistant",
            password_hash=hash_password("assist123"),
            full_name="Морозов Дмитрий Игоревич",
            phone="+7 (922) 222-33-44",
            email="morozov.assist@example.ru",
            inn="667111223344",
            is_active=True,
        )
        db.add(assistant_user)
        db.flush()

        db.add(
            EmployeeCard(
                id_user=assistant_user.id_user,
                id_position=positions["Помощник риэлтора"].id_position,
                experience_years=3,
                description=(
                    "Координация показов объектов, подготовка проектов договоров и "
                    "первичная проверка комплектности документов."
                ),
                rating=Decimal("4.9"),
            )
        )

    # 4. Демо-клиенты (если таблица пуста, а также гарантируем валидный пароль у существующих)
    if db.query(Client).count() == 0:
        demo_clients = [
            {
                "login": "client_ivanov",
                "full_name": "Иванов Сергей Петрович",
                "phone": "+7 (912) 111-22-33",
                "email": "ivanov.sp@example.ru",
                "inn": "665812345678",
                "passport": {
                    "passport_series": "6518",
                    "passport_number": "456789",
                    "issue_date": date(2018, 5, 14),
                    "department_code": "660-001",
                    "issued_by": "ГУ МВД России по Свердловской области",
                },
                "budget": Decimal("9500000.00"),
                "district": districts["Центр"].id_district,
                "source": lead_sources["Сайт (О себе)"].id_lead_source,
                "tier": client_tiers["Стандарт"].id_client_tier,
                "notes": "Покупатель. Ищет 2-комнатную квартиру.",
            },
            {
                "login": "client_petrova",
                "full_name": "Петрова Анна Владимировна",
                "phone": "+7 (922) 444-55-66",
                "email": "petrova.av@example.ru",
                "inn": "667098765432",
                "passport": {
                    "passport_series": "6520",
                    "passport_number": "912345",
                    "issue_date": date(2020, 9, 21),
                    "department_code": "660-014",
                    "issued_by": "Отделением УФМС по Ленинскому району г. Екатеринбурга",
                },
                "budget": Decimal("12000000.00"),
                "district": districts["ВИЗ"].id_district,
                "source": lead_sources["Рекомендация"].id_lead_source,
                "tier": client_tiers["VIP"].id_client_tier,
                "notes": "Собственник / продавец объекта.",
            },
            {
                "login": "client_sidorov",
                "full_name": "Сидоров Алексей Дмитриевич",
                "phone": "+7 (904) 777-88-99",
                "email": "sidorov.ad@example.ru",
                "inn": "667155544433",
                "passport": {
                    "passport_series": "6515",
                    "passport_number": "102938",
                    "issue_date": date(2015, 3, 10),
                    "department_code": "660-007",
                    "issued_by": "ОУФМС России по Свердловской области в Чкаловском районе",
                },
                "budget": Decimal("15500000.00"),
                "district": districts["Ботаника"].id_district,
                "source": lead_sources["Повторное обращение"].id_lead_source,
                "tier": client_tiers["Инвестор"].id_client_tier,
                "notes": "Арендатор / инвестор коммерческого помещения.",
            },
        ]

        for item in demo_clients:
            user = User(
                id_role=roles["Клиент"].id_role,
                login=item["login"],
                password_hash=hash_password("client123"),
                full_name=item["full_name"],
                phone=item["phone"],
                email=item["email"],
                inn=item["inn"],
                is_active=True,
            )
            db.add(user)
            db.flush()

            p = item["passport"]
            db.add(
                PassportData(
                    id_user=user.id_user,
                    passport_series=p["passport_series"],
                    passport_number=p["passport_number"],
                    issue_date=p["issue_date"],
                    department_code=p["department_code"],
                    issued_by=p["issued_by"],
                )
            )
            db.add(
                Client(
                    id_user=user.id_user,
                    id_lead_source=item["source"],
                    id_client_tier=item["tier"],
                    preferred_budget_max=item["budget"],
                    id_preferred_district=item["district"],
                    notes=item["notes"],
                )
            )
    else:
        # Обновляем placeholder-хэш, если база осталась от 1-й итерации
        for u in db.query(User).filter(User.password_hash == "demo_placeholder_hash").all():
            u.password_hash = hash_password("client123")

    db.flush()

    # 5. Демо-объекты недвижимости
    if db.query(Property).count() == 0:
        db.add_all(
            [
                Property(
                    cadastral_number="66:41:0401005:1024",
                    address="г. Екатеринбург, ул. Радищева, д. 33, кв. 48",
                    id_district=districts["Центр"].id_district,
                    total_area=Decimal("64.50"),
                    rooms_count=2,
                    floor=7,
                    id_building_type=building_types["Монолитный"].id_building_type,
                    id_repair_type=repair_types["Евроремонт"].id_repair_type,
                    id_property_type=categories["Квартира"].id_property_type,
                    id_status=prop_statuses["Доступен"].id_status,
                    price=Decimal("8950000.00"),
                    location_rating=Decimal("9.4"),
                    description="Светлая двухкомнатная квартира в самом центре города, рядом с метро и парком.",
                ),
                Property(
                    cadastral_number="66:41:0302011:518",
                    address="г. Екатеринбург, ул. Татищева, д. 77, кв. 112",
                    id_district=districts["ВИЗ"].id_district,
                    total_area=Decimal("82.00"),
                    rooms_count=3,
                    floor=12,
                    id_building_type=building_types["Кирпичный"].id_building_type,
                    id_repair_type=repair_types["Дизайнерский"].id_repair_type,
                    id_property_type=categories["Квартира"].id_property_type,
                    id_status=prop_statuses["Доступен"].id_status,
                    price=Decimal("11400000.00"),
                    location_rating=Decimal("8.9"),
                    description="Просторная трехкомнатная квартира с дизайнерской отделкой и видом на пруд.",
                ),
                Property(
                    cadastral_number="66:41:0504002:89",
                    address="г. Екатеринбург, ул. Белинского, д. 163, пом. 4",
                    id_district=districts["Ботаника"].id_district,
                    total_area=Decimal("115.00"),
                    rooms_count=4,
                    floor=1,
                    id_building_type=building_types["Монолитный"].id_building_type,
                    id_repair_type=repair_types["Косметический"].id_repair_type,
                    id_property_type=categories["Коммерция"].id_property_type,
                    id_status=prop_statuses["Доступен"].id_status,
                    price=Decimal("14800000.00"),
                    location_rating=Decimal("9.1"),
                    description="Помещение свободного назначения на первой линии с отдельным входом.",
                ),
                Property(
                    cadastral_number="66:41:0601014:307",
                    address="г. Екатеринбург, ул. Вильгельма де Геннина, д. 42, кв. 19",
                    id_district=districts["Академический"].id_district,
                    total_area=Decimal("52.30"),
                    rooms_count=2,
                    floor=5,
                    id_building_type=building_types["Панельный"].id_building_type,
                    id_repair_type=repair_types["Косметический"].id_repair_type,
                    id_property_type=categories["Квартира"].id_property_type,
                    id_status=prop_statuses["Забронирован"].id_status,
                    price=Decimal("6350000.00"),
                    location_rating=Decimal("8.3"),
                    description="Уютная семейная квартира рядом со школой и Преображенским парком.",
                ),
            ]
        )
        db.flush()

    # 6. Демо-отзывы (часть одобрена для показа на странице «О себе», один на модерации)
    ivanov_user = db.query(User).filter(User.login == "client_ivanov").first()
    petrova_user = db.query(User).filter(User.login == "client_petrova").first()
    sidorov_user = db.query(User).filter(User.login == "client_sidorov").first()

    if db.query(Review).count() == 0 and ivanov_user and petrova_user and sidorov_user:
        db.add_all(
            [
                Review(
                    author_user_id=ivanov_user.id_user,
                    target_user_id=realtor_user.id_user,
                    review_text=(
                        "Ольга Геннадьевна провела сложную альтернативную сделку за 3 недели. "
                        "Все договоры были готовы заранее, в банке и Росреестре всё прошло без единой заминки."
                    ),
                    rating=5,
                    is_approved=True,
                ),
                Review(
                    author_user_id=petrova_user.id_user,
                    target_user_id=realtor_user.id_user,
                    review_text=(
                        "Продавала трехкомнатную квартиру на ВИЗе. Грамотная оценка цены, качественные показы "
                        "и полный контроль эскроу-счета. Очень рекомендую!"
                    ),
                    rating=5,
                    is_approved=True,
                ),
                Review(
                    author_user_id=sidorov_user.id_user,
                    target_user_id=realtor_user.id_user,
                    review_text=(
                        "Подбирали коммерческое помещение под офис. Быстро нашли 4 подходящих варианта, "
                        "проверили юридическую чистоту собственника и согласовали выгодный договор."
                    ),
                    rating=5,
                    is_approved=True,
                ),
                Review(
                    author_user_id=ivanov_user.id_user,
                    target_user_id=assistant_user.id_user,
                    review_text="Дмитрий оперативно организовал два показа в один день и ответил на все вопросы по дому.",
                    rating=5,
                    is_approved=False,
                ),
            ]
        )

    # 7. Демо-сделка, показ, обращение и уведомления
    first_prop = db.query(Property).order_by(Property.id_property.asc()).first()
    ivanov_client = (
        db.query(Client).filter(Client.id_user == ivanov_user.id_user).first()
        if ivanov_user
        else None
    )
    petrova_client = (
        db.query(Client).filter(Client.id_user == petrova_user.id_user).first()
        if petrova_user
        else None
    )

    if db.query(Deal).count() == 0 and first_prop and ivanov_client and petrova_client:
        deal = Deal(
            id_property=first_prop.id_property,
            responsible_realtor_id=realtor_user.id_user,
            id_deal_type=deal_types["Купля-продажа"].id_deal_type,
            id_deal_status=deal_statuses["Подготовка документов"].id_deal_status,
            id_escrow_status=escrow_statuses["Открыт"].id_escrow_status,
            final_price=first_prop.price,
            commission_rate=Decimal("2.50"),
            start_date=date.today() - timedelta(days=5),
        )
        db.add(deal)
        db.flush()
        db.add_all(
            [
                DealParticipant(
                    id_deal=deal.id_deal,
                    id_client=ivanov_client.id_client,
                    id_client_role=client_roles["Покупатель"].id_client_role,
                ),
                DealParticipant(
                    id_deal=deal.id_deal,
                    id_client=petrova_client.id_client,
                    id_client_role=client_roles["Продавец"].id_client_role,
                ),
            ]
        )

    if db.query(PropertyShowing).count() == 0 and first_prop and ivanov_client:
        showing_dt = (datetime.now() + timedelta(days=1)).replace(
            hour=15, minute=0, second=0, microsecond=0
        )
        db.add(
            PropertyShowing(
                id_property=first_prop.id_property,
                id_client=ivanov_client.id_client,
                id_realtor=realtor_user.id_user,
                id_showing_status=showing_statuses["Запланирован"].id_showing_status,
                showing_datetime=showing_dt,
                result_comment="Повторный осмотр перед подписанием договора.",
            )
        )

    if db.query(Inquiry).count() == 0 and first_prop:
        db.add(
            Inquiry(
                id_property=first_prop.id_property,
                full_name="Кузнецова Мария Олеговна",
                phone="+7 (912) 555-12-34",
                email="kuznetsova@example.ru",
                inquiry_type="Запись на просмотр",
                message="Добрый день! Хотела бы посмотреть квартиру на ул. Радищева в субботу днем.",
                status="Новое",
                assigned_realtor_id=realtor_user.id_user,
            )
        )

    if db.query(Notification).count() == 0 and ivanov_user:
        db.add(
            Notification(
                id_user=ivanov_user.id_user,
                message_text="Вам назначен показ объекта по адресу ул. Радищева, д. 33 на завтра в 15:00.",
                is_read=False,
            )
        )

    # 8. Стартовый шаблон .docx
    if db.query(ContractTemplate).count() == 0:
        sample_filename = "sample_contract_template.docx"
        sample_path = settings.templates_dir / sample_filename
        create_sample_template_docx(sample_path)
        tags = extract_tags_from_docx(sample_path)
        db.add(
            ContractTemplate(
                template_name="Договор оказания риэлторских услуг (пример)",
                file_path=sample_filename,
                detected_tags=json.dumps(tags, ensure_ascii=False),
                is_active=True,
            )
        )

    db.commit()
