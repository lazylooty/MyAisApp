from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)


class Base(DeclarativeBase):
    pass


def ensure_schema_upgrades() -> None:
    """Safely add new columns to existing PostgreSQL tables when upgrading an existing DB volume."""
    statements = [
        "ALTER TABLE client ADD COLUMN IF NOT EXISTS id_lead_source INTEGER REFERENCES lead_source(id_lead_source)",
        "ALTER TABLE client ADD COLUMN IF NOT EXISTS id_client_tier INTEGER REFERENCES client_tier(id_client_tier)",
        "ALTER TABLE contract ADD COLUMN IF NOT EXISTS id_deal INTEGER REFERENCES deal(id_deal) ON DELETE SET NULL",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS hero_title VARCHAR(255) NOT NULL DEFAULT 'Недвижимость с безупречной юридической чистотой'",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS hero_subtitle TEXT NOT NULL DEFAULT 'Персональное сопровождение сделок купли-продажи и аренды жилой и коммерческой недвижимости в Екатеринбурге. Проверка объектов, эскроу-расчеты и защита ваших интересов.'",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS about_text TEXT NOT NULL DEFAULT 'ИП Голубина Ольга Геннадьевна — это бутиковый подход к каждой сделке. Мы не работаем на поток: каждый объект проходит глубокую правовую проверку ЕГРН, истории переходов права и обременений, а клиент получает прозрачный график показов, аналитику рыночной цены и готовый пакет юридических документов.'",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS stat_years VARCHAR(40) NOT NULL DEFAULT '12+ лет'",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS stat_deals VARCHAR(40) NOT NULL DEFAULT '640+'",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS stat_clients VARCHAR(40) NOT NULL DEFAULT '1 100+'",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS stat_satisfaction VARCHAR(40) NOT NULL DEFAULT '99%'",
        "ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS reviews_require_moderation BOOLEAN NOT NULL DEFAULT TRUE",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
