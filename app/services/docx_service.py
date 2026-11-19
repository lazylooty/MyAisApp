import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from docx import Document
from docx.shared import Pt

from app.models import AppSettings, Client, Deal, Property

TAG_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
USER_PREFIX_RE = re.compile(
    r"^(?P<field>[A-Z0-9_.]+)\.(?:USER|CLIENT)(?:[\(_]*(?P<idx>\d+)\)?)?$"
)
USER_FIRST_RE = re.compile(
    r"^(?:USER|CLIENT)(?:[\(_]*(?P<idx>\d+)\)?)?\.(?P<field>[A-Z0-9_.]+)$"
)


def _iter_all_paragraphs(doc: Document) -> Iterable:
    for paragraph in doc.paragraphs:
        yield paragraph

    def _walk_tables(tables) -> Iterable:
        for table in tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        yield paragraph
                    yield from _walk_tables(cell.tables)

    yield from _walk_tables(doc.tables)

    for section in doc.sections:
        for header_or_footer in (
            section.header,
            section.first_page_header,
            section.even_page_header,
            section.footer,
            section.first_page_footer,
            section.even_page_footer,
        ):
            if header_or_footer is None:
                continue
            for paragraph in header_or_footer.paragraphs:
                yield paragraph
            yield from _walk_tables(header_or_footer.tables)


def extract_tags_from_docx(docx_path: Path) -> List[str]:
    """Read a .docx file and return a unique ordered list of {{ ... }} placeholder tags."""
    doc = Document(str(docx_path))
    found: List[str] = []
    seen = set()
    for paragraph in _iter_all_paragraphs(doc):
        text = paragraph.text or ""
        for match in TAG_PATTERN.finditer(text):
            tag_name = match.group(1).strip()
            if tag_name not in seen:
                seen.add(tag_name)
                found.append(tag_name)
    return found


def _format_money(value: Decimal | float | int | None) -> str:
    if value is None:
        return ""
    num = Decimal(str(value))
    return f"{num:,.2f}".replace(",", " ")


def _format_date(value: Optional[date]) -> str:
    if not value:
        return ""
    return value.strftime("%d.%m.%Y")


def _resolve_client_field(client: Client, field: str) -> str:
    user = client.user
    passport = user.passport
    normalized = field.upper().replace(".", "_")

    if normalized in ("FIO", "FULL_NAME", "NAME"):
        return user.full_name or ""
    if normalized == "INN":
        return user.inn or "не указан"
    if normalized == "PHONE":
        return user.phone or ""
    if normalized == "EMAIL":
        return user.email or ""
    if normalized in ("PASSPORT_SERIES", "PASSPORT_SERIA"):
        return passport.passport_series if passport else ""
    if normalized in ("PASSPORT_NUMBER", "PASSPORT_NUM"):
        return passport.passport_number if passport else ""
    if normalized in ("PASSPORT_ISSUE_DATE", "PASSPORT_DATE"):
        return _format_date(passport.issue_date) if passport else ""
    if normalized in ("PASSPORT_ISSUED_BY", "PASSPORT_KEM_VYDAN"):
        return passport.issued_by if passport else ""
    if normalized in ("PASSPORT_DEPT_CODE", "PASSPORT_DEPARTMENT_CODE", "PASSPORT_CODE"):
        return passport.department_code if passport else ""
    if normalized in ("PASSPORT", "PASSPORT_FULL"):
        if not passport:
            return "паспортные данные не заполнены"
        return (
            f"серия {passport.passport_series} № {passport.passport_number}, "
            f"выдан {passport.issued_by} {_format_date(passport.issue_date)}, "
            f"код подразделения {passport.department_code}"
        )
    return ""


def _resolve_property_field(prop: Property, field: str) -> str:
    normalized = field.upper().replace(".", "_")
    if normalized == "ADDRESS":
        return prop.address or ""
    if normalized in ("CADASTRAL", "CADASTRAL_NUMBER"):
        return prop.cadastral_number or ""
    if normalized in ("AREA", "TOTAL_AREA"):
        return f"{prop.total_area:.2f}"
    if normalized in ("ROOMS", "ROOMS_COUNT"):
        return str(prop.rooms_count)
    if normalized == "FLOOR":
        return str(prop.floor)
    if normalized == "PRICE":
        return _format_money(prop.price)
    if normalized == "PRICE_PER_SQM":
        if prop.total_area and prop.total_area > 0:
            return _format_money(prop.price / prop.total_area)
        return ""
    if normalized == "DISTRICT":
        return prop.district.name if prop.district else ""
    if normalized in ("CATEGORY", "TYPE", "PROPERTY_TYPE"):
        return prop.category.name if prop.category else ""
    if normalized == "BUILDING_TYPE":
        return prop.building_type.name if prop.building_type else ""
    if normalized == "REPAIR_TYPE":
        return prop.repair_type.name if prop.repair_type else ""
    if normalized == "STATUS":
        return prop.status.name if prop.status else ""
    if normalized == "DESCRIPTION":
        return prop.description or ""
    return ""


def _resolve_deal_field(deal: Deal, field: str) -> str:
    normalized = field.upper().replace(".", "_")
    if normalized in ("PRICE", "FINAL_PRICE"):
        return _format_money(deal.final_price)
    if normalized in ("COMMISSION", "COMMISSION_RATE"):
        return f"{deal.commission_rate:.2f}%"
    if normalized == "TYPE":
        return deal.deal_type.name if deal.deal_type else ""
    if normalized == "STATUS":
        return deal.deal_status.name if deal.deal_status else ""
    if normalized in ("ESCROW", "ESCROW_STATUS"):
        return deal.escrow_status.name if deal.escrow_status else ""
    if normalized == "START_DATE":
        return _format_date(deal.start_date)
    if normalized == "REALTOR":
        return deal.realtor.full_name if deal.realtor else ""
    return ""


def resolve_tag_value(
    raw_tag: str,
    clients: Sequence[Client],
    prop: Optional[Property],
    agency: Optional[AppSettings],
    contract_number: str,
    deal: Optional[Deal] = None,
) -> Optional[str]:
    """Resolve {{ ... }} tag values for clients, property, deal, agency, and contract."""
    expr = raw_tag.strip().upper()

    if expr in ("CONTRACT.NUMBER", "DOC.NUMBER"):
        return contract_number
    if expr in ("CONTRACT.DATE", "DOC.DATE", "DATE", "TODAY"):
        return date.today().strftime("%d.%m.%Y")

    if expr.startswith("AGENCY.") and agency is not None:
        sub = expr.split(".", 1)[1]
        mapping: Dict[str, str] = {
            "NAME": agency.agency_name,
            "INN": agency.agency_inn,
            "PHONE": agency.agency_phone,
            "EMAIL": agency.agency_email,
            "ADDRESS": agency.agency_address,
        }
        if sub in mapping:
            return mapping[sub]

    if expr.startswith("DEAL.") and deal is not None:
        sub = expr.split(".", 1)[1]
        val = _resolve_deal_field(deal, sub)
        if val != "":
            return val

    if expr.startswith("PROPERTY.") and prop is not None:
        sub = expr.split(".", 1)[1]
        val = _resolve_property_field(prop, sub)
        if val != "" or sub in ("DESCRIPTION",):
            return val

    match = USER_PREFIX_RE.match(expr) or USER_FIRST_RE.match(expr)
    if match:
        idx_str = match.group("idx")
        index = int(idx_str) - 1 if idx_str else 0
        field = match.group("field")
        if 0 <= index < len(clients):
            return _resolve_client_field(clients[index], field)
        return ""

    return None


def _replace_tags_in_paragraph(
    paragraph,
    clients: Sequence[Client],
    prop: Optional[Property],
    agency: Optional[AppSettings],
    contract_number: str,
    deal: Optional[Deal] = None,
) -> None:
    runs = paragraph.runs
    if not runs:
        return

    run_spans: List[Tuple[int, int, object]] = []
    cursor = 0
    for run in runs:
        text = run.text or ""
        end = cursor + len(text)
        run_spans.append((cursor, end, run))
        cursor = end

    full_text = "".join(r.text or "" for r in runs)
    matches = list(TAG_PATTERN.finditer(full_text))
    if not matches:
        return

    for match in reversed(matches):
        raw_tag = match.group(1)
        replacement = resolve_tag_value(
            raw_tag, clients, prop, agency, contract_number, deal=deal
        )
        if replacement is None:
            continue

        m_start, m_end = match.span()
        placed = False
        for r_start, r_end, run in run_spans:
            if r_end <= m_start or r_start >= m_end:
                continue
            local_start = max(m_start, r_start) - r_start
            local_end = min(m_end, r_end) - r_start
            current_text = run.text or ""
            if not placed:
                run.text = (
                    current_text[:local_start]
                    + replacement
                    + current_text[local_end:]
                )
                placed = True
            else:
                run.text = current_text[:local_start] + current_text[local_end:]


def render_contract_docx(
    template_path: Path,
    output_path: Path,
    clients: Sequence[Client],
    prop: Optional[Property],
    agency: Optional[AppSettings],
    contract_number: str,
    deal: Optional[Deal] = None,
) -> Path:
    """Fill a .docx template with client/property/deal/agency data preserving Word formatting."""
    doc = Document(str(template_path))
    for paragraph in _iter_all_paragraphs(doc):
        _replace_tags_in_paragraph(
            paragraph, clients, prop, agency, contract_number, deal=deal
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path


def create_sample_template_docx(output_path: Path) -> Path:
    """Create a ready-to-test .docx contract template demonstrating {{ FIELD.USER_N }} tags."""
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    title = doc.add_paragraph()
    title.alignment = 1
    r = title.add_run("ДОГОВОР ОКАЗАНИЯ РИЭЛТОРСКИХ УСЛУГ № {{ CONTRACT.NUMBER }}")
    r.bold = True

    meta = doc.add_paragraph()
    meta.add_run("г. Екатеринбург\t\t\t\t\tДата: {{ CONTRACT.DATE }}")

    doc.add_paragraph(
        "Исполнитель: {{ AGENCY.NAME }} (ИНН {{ AGENCY.INN }}, тел. {{ AGENCY.PHONE }}), "
        "с одной стороны, и:"
    )
    doc.add_paragraph(
        "Клиент 1 (Покупатель/Заказчик): {{ FIO.USER(_1) }}, ИНН {{ INN.USER(_1) }}, "
        "паспорт: {{ PASSPORT.USER_1 }}, телефон: {{ PHONE.USER_1 }}, e-mail: {{ EMAIL.USER_1 }}."
    )
    doc.add_paragraph(
        "Клиент 2 (Продавец/Собственник, при наличии): {{ FIO.USER(_2) }}, "
        "ИНН {{ INN.USER(_2) }}, паспорт: {{ PASSPORT.USER_2 }}."
    )

    p_obj = doc.add_paragraph()
    r_obj = p_obj.add_run("Предмет договора (Объект недвижимости):")
    r_obj.bold = True

    table = doc.add_table(rows=5, cols=2)
    table.style = "Table Grid"
    rows_data = [
        ("Адрес объекта", "{{ PROPERTY.ADDRESS }}"),
        ("Кадастровый номер", "{{ PROPERTY.CADASTRAL }}"),
        ("Район / Категория", "{{ PROPERTY.DISTRICT }}, {{ PROPERTY.CATEGORY }}"),
        ("Площадь / Комнаты / Этаж", "{{ PROPERTY.AREA }} м², комн.: {{ PROPERTY.ROOMS }}, этаж {{ PROPERTY.FLOOR }}"),
        ("Стоимость объекта", "{{ PROPERTY.PRICE }} руб."),
    ]
    for idx, (label, tag) in enumerate(rows_data):
        table.rows[idx].cells[0].text = label
        table.rows[idx].cells[1].text = tag

    doc.add_paragraph("")
    doc.add_paragraph("Подписи сторон:")
    doc.add_paragraph("Исполнитель: {{ AGENCY.NAME }} _______________")
    doc.add_paragraph("Клиент 1: {{ FIO.USER_1 }} _______________")
    doc.add_paragraph("Клиент 2: {{ FIO.USER_2 }} _______________")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path
