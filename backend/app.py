from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NoReturn
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    and_,
    asc,
    create_engine,
    desc,
    func,
    or_,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

try:
    import chardet
except Exception:  # pragma: no cover
    chardet = None

try:
    import pdfplumber
except Exception:  # pragma: no cover
    pdfplumber = None


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = BASE_DIR / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'financeiro.db').as_posix()}"
)
ENGINE_KWARGS: dict[str, Any] = {"future": True}
if DATABASE_URL.startswith("sqlite"):
    ENGINE_KWARGS["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **ENGINE_KWARGS)
SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, future=True
)
Base = declarative_base()

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_REQUEST = 20
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20

ALLOWED_MIME_TYPES = {
    "csv": "text/csv",
    "pdf": "application/pdf",
}

BATCH_STATUS_VALUES = {"processing", "completed", "partial_failure", "failed"}
FILE_STATUS_VALUES = {"queued", "processing", "completed", "failed"}

DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d/%m/%y",
    "%m/%d/%Y",
    "%d.%m.%Y",
    "%d.%m.%y",
]

DATE_RE = r"(?P<date>\d{2}[/\-\.]\d{2}[/\-\.]\d{2,4})"
DESCRIPTION_RE = r"(?P<description>.+?)"
AMOUNT_RE = r"(?P<amount>-?[\d.,]+)"
PDF_LINE_PATTERN = re.compile(rf"{DATE_RE}\s+{DESCRIPTION_RE}\s+{AMOUNT_RE}\s*$")

DATE_HEADER_PATTERNS = (r"^data$", r"^date$", r"^dt$", r"^fecha$")
DESCRIPTION_HEADER_PATTERNS = (
    r"descri",
    r"description",
    r"historico",
    r"histórico",
    r"memo",
    r"detail",
)
AMOUNT_HEADER_PATTERNS = (
    r"^valor$",
    r"^value$",
    r"^amount$",
    r"^quantia$",
    r"^montante$",
)
CREDIT_HEADER_PATTERNS = (r"cr[eé]dito", r"^credit$", r"^entrada$")
DEBIT_HEADER_PATTERNS = (r"d[eé]bito", r"^debit$", r"^sa[ií]da$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def raise_api_error(status_code: int, code: str, message: str) -> NoReturn:
    raise HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )


def sanitize_uuid(value: str | None, field_name: str = "value") -> str | None:
    if value is None or value == "":
        return None
    try:
        from uuid import UUID

        return str(UUID(str(value)))
    except Exception:
        raise_api_error(422, "VALIDATION_ERROR", f"Invalid {field_name}.")


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_description(text: str) -> str:
    return normalize_spaces(text)[:500]


def normalize_hash_description(text: str) -> str:
    return strip_accents(normalize_spaces(text).lower())


def parse_date(value: str) -> date:
    raw = normalize_spaces(value)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date '{value}'")


def parse_amount(value: str) -> Decimal:
    raw = normalize_spaces(value)
    if not raw:
        raise ValueError("Empty amount")

    negative = False
    if raw.startswith("(") and raw.endswith(")"):
        negative = True
        raw = raw[1:-1]

    if raw.endswith("-"):
        negative = True
        raw = raw[:-1]

    if raw.startswith("-"):
        negative = True
        raw = raw[1:]

    cleaned = re.sub(r"[^\d,.\-]", "", raw).replace(" ", "")
    if not cleaned:
        raise ValueError("Empty amount")

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    amount = Decimal(cleaned)
    if negative:
        amount = -abs(amount)

    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_hash(date_value: date, description: str, amount: Decimal) -> str:
    date_iso = date_value.isoformat()
    normalized_desc = normalize_hash_description(description)
    normalized_amount = f"{abs(amount):.2f}"
    canonical = f"{date_iso}|{normalized_desc}|{normalized_amount}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


SYSTEM_CATEGORY_NAME = "Uncategorized"
CATEGORY_COLOR_DEFAULT = "#6B7280"
SYSTEM_CATEGORY_COLOR = "#9CA3AF"
CATEGORY_NAME_MAX = 100
RULE_KEYWORD_MAX = 255
MATCH_TYPES = {"exact", "contains", "starts_with", "ends_with"}
CATEGORY_SOURCES = {"manual", "learned", "system"}
TRANSACTION_CATEGORIZATION_SOURCES = {"auto", "manual", "bulk"}

_categorization_lock = threading.Lock()


def normalize_text(text: str) -> str:
    return normalize_spaces(strip_accents(text).lower())


def normalize_category_name(text: str) -> str:
    return normalize_spaces(text)


def normalize_rule_keyword(text: str) -> str:
    return normalize_text(text)


def is_valid_hex_color(value: str) -> bool:
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", value))


def serialize_category(category: "Category") -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "color": category.color,
        "icon": category.icon,
        "is_system": category.is_system,
        "created_at": isoformat_z(category.created_at),
        "updated_at": isoformat_z(category.updated_at),
    }


def serialize_rule(session: Session, rule: "CategorizationRule") -> dict[str, Any]:
    category = session.get(Category, rule.category_id)
    return {
        "id": rule.id,
        "keyword": rule.keyword,
        "category_id": rule.category_id,
        "category_name": category.name if category else None,
        "match_type": rule.match_type,
        "priority": rule.priority,
        "source": rule.source,
        "is_active": rule.is_active,
        "created_at": isoformat_z(rule.created_at),
        "updated_at": isoformat_z(rule.updated_at),
    }


def serialize_transaction(
    session: Session, transaction: "Transaction"
) -> dict[str, Any]:
    category = (
        session.get(Category, transaction.category_id)
        if transaction.category_id
        else None
    )
    file_row = (
        session.get(ImportFile, transaction.import_file_id)
        if transaction.import_file_id
        else None
    )
    import_id = file_row.batch_id if file_row else None
    return {
        "id": transaction.id,
        "date": transaction.date.isoformat(),
        "description": transaction.description,
        "original_description": transaction.description,
        "amount": float(transaction.amount),
        "category_id": transaction.category_id,
        "category_name": category.name if category else None,
        "account_id": transaction.account_id,
        "account_name": None,
        "import_id": import_id,
        "created_at": isoformat_z(transaction.created_at),
        "updated_at": isoformat_z(transaction.updated_at),
    }


def validate_category_payload(
    payload: dict[str, Any], allow_partial: bool = False
) -> dict[str, Any]:
    allowed = {"name", "color", "icon"}
    unknown = set(payload) - allowed
    if unknown:
        raise_api_error(400, "INVALID_CATEGORY_NAME", "Unexpected fields in request.")

    data = dict(payload)

    if not allow_partial or "name" in data:
        name = data.get("name")
        if not isinstance(name, str):
            raise_api_error(
                400,
                "INVALID_CATEGORY_NAME",
                "Category name must be between 1 and 100 characters.",
            )
        name = normalize_category_name(name)
        if not (1 <= len(name) <= CATEGORY_NAME_MAX):
            raise_api_error(
                400,
                "INVALID_CATEGORY_NAME",
                "Category name must be between 1 and 100 characters.",
            )
        data["name"] = name

    if "color" in data:
        color = data.get("color")
        if color is None:
            data.pop("color")
        else:
            if not isinstance(color, str) or not is_valid_hex_color(color):
                raise_api_error(
                    400,
                    "INVALID_COLOR_FORMAT",
                    "Color must be a valid hex code (e.g., #FF5733).",
                )
            data["color"] = color

    if "icon" in data:
        icon = data.get("icon")
        if icon is None:
            data.pop("icon")
        else:
            if not isinstance(icon, str):
                raise_api_error(400, "VALIDATION_ERROR", "Category icon must be text.")
            icon = normalize_spaces(icon)
            if len(icon) > 50:
                raise_api_error(
                    400, "VALIDATION_ERROR", "Category icon must be 50 chars or less."
                )
            data["icon"] = icon

    return data


def validate_rule_payload(
    payload: dict[str, Any], allow_partial: bool = False
) -> dict[str, Any]:
    allowed = {"keyword", "category_id", "match_type", "priority", "is_active"}
    unknown = set(payload) - allowed
    if unknown:
        raise_api_error(400, "INVALID_KEYWORD", "Unexpected fields in request.")

    data = dict(payload)

    if not allow_partial or "keyword" in data:
        keyword = data.get("keyword")
        if not isinstance(keyword, str):
            raise_api_error(
                400, "INVALID_KEYWORD", "Keyword must be between 1 and 255 characters."
            )
        keyword = normalize_rule_keyword(keyword)
        if not (1 <= len(keyword) <= RULE_KEYWORD_MAX):
            raise_api_error(
                400, "INVALID_KEYWORD", "Keyword must be between 1 and 255 characters."
            )
        data["keyword"] = keyword

    if not allow_partial or "category_id" in data:
        category_id = data.get("category_id")
        if category_id in (None, ""):
            raise_api_error(404, "CATEGORY_NOT_FOUND", "Category id required.")
        try:
            data["category_id"] = int(category_id)
        except Exception:
            raise_api_error(422, "VALIDATION_ERROR", "category_id must be an integer.")

    if "match_type" in data:
        match_type = data.get("match_type", "contains")
        if not isinstance(match_type, str) or match_type not in MATCH_TYPES:
            raise_api_error(
                400,
                "INVALID_MATCH_TYPE",
                "match_type must be one of: exact, contains, starts_with, ends_with.",
            )
        data["match_type"] = match_type

    if "priority" in data:
        priority = data.get("priority", 50)
        if isinstance(priority, bool):
            raise_api_error(422, "VALIDATION_ERROR", "priority must be an integer.")
        try:
            priority_int = int(priority)
        except Exception:
            raise_api_error(422, "VALIDATION_ERROR", "priority must be an integer.")
        if priority_int < 0:
            priority_int = 0
        data["priority"] = priority_int

    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            raise_api_error(422, "VALIDATION_ERROR", "is_active must be true or false.")

    return data


def validate_transaction_ids(value: Any) -> list[int]:
    if not isinstance(value, list) or not value:
        raise_api_error(
            400,
            "EMPTY_TRANSACTION_LIST",
            "transaction_ids must contain at least one ID.",
        )
    if len(value) > 500:
        raise_api_error(
            400, "TOO_MANY_TRANSACTIONS", "Maximum 500 transactions per bulk operation."
        )

    ids = []
    seen = set()
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise_api_error(
                422, "VALIDATION_ERROR", "transaction_ids must contain integers."
            )
        if item in seen:
            raise_api_error(
                400,
                "EMPTY_TRANSACTION_LIST",
                "transaction_ids must contain unique IDs.",
            )
        seen.add(item)
        ids.append(item)
    return ids


def get_category_or_404(session: Session, category_id: int) -> "Category":
    category = session.get(Category, category_id)
    if category is None:
        raise_api_error(
            404, "CATEGORY_NOT_FOUND", f"Category with id {category_id} does not exist."
        )
    return category


def get_rule_or_404(session: Session, rule_id: int) -> "CategorizationRule":
    rule = session.get(CategorizationRule, rule_id)
    if rule is None:
        raise_api_error(
            404, "RULE_NOT_FOUND", f"Rule with id {rule_id} does not exist."
        )
    return rule


def get_transaction_or_404(session: Session, transaction_id: int) -> "Transaction":
    transaction = session.get(Transaction, transaction_id)
    if transaction is None:
        raise_api_error(
            404,
            "TRANSACTION_NOT_FOUND",
            f"Transaction with id {transaction_id} does not exist.",
        )
    return transaction


def ensure_system_category(session: Session) -> None:
    existing = session.execute(
        select(Category).where(
            func.lower(Category.name) == SYSTEM_CATEGORY_NAME.lower()
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            Category(
                name=SYSTEM_CATEGORY_NAME,
                color=SYSTEM_CATEGORY_COLOR,
                icon=None,
                is_system=True,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
        session.commit()


def rule_matches(normalized_description: str, keyword: str, match_type: str) -> bool:
    if match_type == "exact":
        return normalized_description == keyword
    if match_type == "contains":
        return keyword in normalized_description
    if match_type == "starts_with":
        return normalized_description.startswith(keyword)
    if match_type == "ends_with":
        return normalized_description.endswith(keyword)
    return False


def active_rules(session: Session) -> list["CategorizationRule"]:
    return (
        session.execute(
            select(CategorizationRule)
            .where(CategorizationRule.is_active.is_(True))
            .order_by(CategorizationRule.priority.desc(), CategorizationRule.id.asc())
        )
        .scalars()
        .all()
    )


def apply_transaction_category(
    session: Session,
    transaction: "Transaction",
    category_id: int | None,
    source: str,
) -> None:
    transaction.category_id = category_id
    transaction.categorized_at = utc_now()
    transaction.categorization_source = source
    transaction.updated_at = utc_now()


def learn_rule_from_transaction(
    session: Session,
    transaction: "Transaction",
    category_id: int | None,
) -> CategorizationRule | None:
    if category_id is None:
        return None

    keyword = normalize_rule_keyword(transaction.description)
    existing = session.execute(
        select(CategorizationRule).where(
            CategorizationRule.keyword == keyword,
            CategorizationRule.match_type == "contains",
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.category_id == category_id:
            return existing
        existing.category_id = category_id
        existing.updated_at = utc_now()
        return existing

    rule = CategorizationRule(
        keyword=keyword,
        category_id=category_id,
        match_type="contains",
        priority=10,
        source="learned",
        is_active=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(rule)
    return rule


def categorize_transactions(
    session: Session,
    scope: str = "uncategorized",
    account_id: str | None = None,
) -> dict[str, Any]:
    query = select(Transaction)
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if scope == "uncategorized":
        query = query.where(Transaction.category_id.is_(None))
    elif scope != "all":
        raise_api_error(400, "INVALID_SCOPE", "scope must be uncategorized or all.")

    rows = session.execute(query.order_by(Transaction.id.asc())).scalars().all()
    rules = active_rules(session)
    processed = 0
    categorized = 0
    uncategorized = 0

    for transaction in rows:
        if scope == "all" and transaction.categorization_source == "manual":
            continue
        processed += 1
        normalized_description = normalize_text(transaction.description)
        matched_rule = None
        for rule in rules:
            if rule_matches(normalized_description, rule.keyword, rule.match_type):
                matched_rule = rule
                break

        if matched_rule is not None:
            transaction.category_id = matched_rule.category_id
            categorized += 1
        else:
            transaction.category_id = None
            uncategorized += 1

        transaction.categorized_at = utc_now()
        transaction.categorization_source = "auto"
        transaction.updated_at = utc_now()

    session.commit()
    return {
        "processed": processed,
        "categorized": categorized,
        "uncategorized": uncategorized,
    }


def detect_encoding(raw_bytes: bytes) -> str:
    if chardet is not None:
        guess = chardet.detect(raw_bytes[:65536]) or {}
        encoding = guess.get("encoding")
        if encoding:
            return encoding

    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            raw_bytes.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue

    raise_api_error(400, "ENCODING_DETECTION_FAILED", "Could not detect file encoding.")


def decode_text(raw_bytes: bytes) -> str:
    encoding = detect_encoding(raw_bytes)
    try:
        return raw_bytes.decode(encoding)
    except UnicodeDecodeError:
        for fallback in ("utf-8", "cp1252", "latin-1"):
            try:
                return raw_bytes.decode(fallback)
            except UnicodeDecodeError:
                continue
    raise_api_error(400, "ENCODING_DETECTION_FAILED", "Could not decode file contents.")


def detect_delimiter(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()][:5]
    if not lines:
        raise_api_error(
            400, "INVALID_FILE_FORMAT", "Only CSV and PDF files are accepted."
        )

    candidates = [";", ",", "\t"]
    counts = {candidate: 0 for candidate in candidates}

    for line in lines:
        for candidate in candidates:
            counts[candidate] += line.count(candidate)

    best = max(counts, key=lambda candidate: counts[candidate])
    if counts[best] == 0:
        raise_api_error(
            400, "INVALID_FILE_FORMAT", "Only CSV and PDF files are accepted."
        )
    return best


def normalize_header(value: str) -> str:
    return normalize_spaces(strip_accents(value).lower())


def header_matches(header: str, patterns: tuple[str, ...]) -> bool:
    normalized = normalize_header(header)
    return any(
        re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns
    )


def detect_column_roles(headers: list[str]) -> dict[str, int]:
    roles: dict[str, int] = {}

    for index, header in enumerate(headers):
        if "date" not in roles and header_matches(header, DATE_HEADER_PATTERNS):
            roles["date"] = index
        if "description" not in roles and header_matches(
            header, DESCRIPTION_HEADER_PATTERNS
        ):
            roles["description"] = index
        if "amount" not in roles and header_matches(header, AMOUNT_HEADER_PATTERNS):
            roles["amount"] = index
        if "credit" not in roles and header_matches(header, CREDIT_HEADER_PATTERNS):
            roles["credit"] = index
        if "debit" not in roles and header_matches(header, DEBIT_HEADER_PATTERNS):
            roles["debit"] = index

    if (
        "date" not in roles
        or "description" not in roles
        or ("amount" not in roles and not ("credit" in roles or "debit" in roles))
    ):
        raise_api_error(
            400, "COLUMN_MAPPING_FAILED", "Could not map required CSV columns."
        )

    return roles


def detect_file_type(raw_bytes: bytes) -> str:
    if raw_bytes.startswith(b"%PDF"):
        return "pdf"

    try:
        text = decode_text(raw_bytes)
    except HTTPException:
        raise_api_error(
            400, "INVALID_FILE_FORMAT", "Only CSV and PDF files are accepted."
        )

    if any(delimiter in text for delimiter in (";", ",", "\t")) and any(
        line.strip() for line in text.splitlines()
    ):
        return "csv"

    raise_api_error(400, "INVALID_FILE_FORMAT", "Only CSV and PDF files are accepted.")


def row_to_raw_string(row: list[str], delimiter: str) -> str:
    return delimiter.join(row)


@dataclass
class ParsedRow:
    date_value: date
    description: str
    amount: Decimal
    transaction_type: str
    hash_value: str
    raw_data: Any


@dataclass
class ParseErrorItem:
    row_number: int | None
    raw_data: str | None
    error_type: str
    error_message: str


@dataclass
class ParseResult:
    rows: list[ParsedRow]
    errors: list[ParseErrorItem]
    fatal: bool = False
    fatal_code: str | None = None
    fatal_message: str | None = None


class ImportBatch(Base):
    __tablename__ = "import_batch"

    id = Column(String(36), primary_key=True)
    account_id = Column(String(36), nullable=True)
    status = Column(String(20), nullable=False, default="processing")
    file_count = Column(Integer, nullable=False, default=0)
    total_created = Column(Integer, nullable=False, default=0)
    total_skipped = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ImportFile(Base):
    __tablename__ = "import_file"

    id = Column(String(36), primary_key=True)
    batch_id = Column(String(36), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(512), nullable=False)
    mime_type = Column(String(50), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    rows_extracted = Column(Integer, nullable=False, default=0)
    rows_failed = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ImportErrorModel(Base):
    __tablename__ = "import_error"

    id = Column(String(36), primary_key=True)
    file_id = Column(String(36), nullable=False, index=True)
    row_number = Column(Integer, nullable=True)
    raw_data = Column(Text, nullable=True)
    error_type = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True, autoincrement=True)
    import_file_id = Column(String(36), nullable=True, index=True)
    account_id = Column(String(36), nullable=True)
    date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    type = Column(String(10), nullable=False)
    category_id = Column(Integer, nullable=True, index=True)
    categorized_at = Column(DateTime(timezone=True), nullable=True)
    categorization_source = Column(String(20), nullable=True)
    hash = Column(String(64), nullable=False, unique=True, index=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    color = Column(String(7), nullable=False, default=CATEGORY_COLOR_DEFAULT)
    icon = Column(String(50), nullable=True)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class CategorizationRule(Base):
    __tablename__ = "categorization_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False)
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    match_type = Column(String(20), nullable=False, default="contains")
    priority = Column(Integer, nullable=False, default=0)
    source = Column(String(20), nullable=False, default="manual")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


Base.metadata.create_all(bind=engine)
with SessionLocal() as _seed_session:
    ensure_system_category(_seed_session)

app = FastAPI(title="Financeiro Ingestion API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def db_session() -> Session:
    return SessionLocal()


def file_path_for(batch_id: str, file_id: str, mime_type: str) -> Path:
    ext = "pdf" if mime_type == "application/pdf" else "csv"
    path = UPLOAD_ROOT / batch_id
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{file_id}.{ext}"


def serialize_file(file_row: ImportFile) -> dict[str, Any]:
    return {
        "file_id": file_row.id,
        "original_filename": file_row.original_filename,
        "mime_type": file_row.mime_type,
        "size_bytes": file_row.size_bytes,
        "status": file_row.status,
        "rows_extracted": file_row.rows_extracted,
        "rows_failed": file_row.rows_failed,
        "error_message": file_row.error_message,
        "created_at": isoformat_z(file_row.created_at),
        "started_at": isoformat_z(file_row.started_at),
        "completed_at": isoformat_z(file_row.completed_at),
    }


def serialize_batch(
    batch_row: ImportBatch, files: list[ImportFile] | None = None
) -> dict[str, Any]:
    payload = {
        "batch_id": batch_row.id,
        "status": batch_row.status,
        "created_at": isoformat_z(batch_row.created_at),
        "files": [],
        "total_transactions_created": batch_row.total_created,
        "duplicates_skipped": batch_row.total_skipped,
    }
    if files is not None:
        payload["files"] = [
            {
                "file_id": file_row.id,
                "original_filename": file_row.original_filename,
                "status": file_row.status,
                "rows_extracted": file_row.rows_extracted,
                "rows_failed": file_row.rows_failed,
                "error_message": file_row.error_message,
            }
            for file_row in files
        ]
    return payload


def serialize_batch_list(batch_row: ImportBatch) -> dict[str, Any]:
    return {
        "batch_id": batch_row.id,
        "status": batch_row.status,
        "file_count": batch_row.file_count,
        "total_transactions_created": batch_row.total_created,
        "created_at": isoformat_z(batch_row.created_at),
    }


def build_error_payload(
    batch_row: ImportBatch,
    error_items: list[ImportErrorModel],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    return {
        "batch_id": batch_row.id,
        "errors": [
            {
                "file_id": item.file_id,
                "original_filename": item.file.original_filename
                if hasattr(item, "file") and item.file
                else None,
                "row_number": item.row_number,
                "raw_data": item.raw_data,
                "error_type": item.error_type,
                "error_message": item.error_message,
            }
            for item in error_items
        ],
        "total": len(error_items),
        "page": page,
        "page_size": page_size,
    }


def build_parsed_row(
    date_raw: str,
    description_raw: str,
    amount_raw: str,
    raw_data: Any,
    credit_raw: str | None = None,
    debit_raw: str | None = None,
) -> ParsedRow:
    if not normalize_spaces(date_raw) or not normalize_spaces(description_raw):
        raise ValueError("Missing required field")

    try:
        parsed_date = parse_date(date_raw)
    except ValueError as exc:
        raise ValueError(f"INVALID_DATE: {exc}") from exc

    signed_amount: Decimal | None = None

    if credit_raw is not None or debit_raw is not None:
        credit_value = normalize_spaces(credit_raw or "")
        debit_value = normalize_spaces(debit_raw or "")

        if credit_value:
            try:
                signed_amount = parse_amount(credit_value)
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(
                    f"INVALID_AMOUNT: Could not parse amount '{credit_value}'"
                ) from exc
        elif debit_value:
            try:
                signed_amount = -abs(parse_amount(debit_value))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(
                    f"INVALID_AMOUNT: Could not parse amount '{debit_value}'"
                ) from exc
        else:
            raise ValueError("MISSING_REQUIRED_FIELD: Amount missing")
    else:
        amount_value = normalize_spaces(amount_raw)
        if not amount_value:
            raise ValueError("MISSING_REQUIRED_FIELD: Amount missing")
        try:
            signed_amount = parse_amount(amount_value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(
                f"INVALID_AMOUNT: Could not parse amount '{amount_value}'"
            ) from exc

    if signed_amount is None:
        raise ValueError("MISSING_REQUIRED_FIELD: Amount missing")

    description = normalize_description(description_raw)
    if not description:
        raise ValueError("MISSING_REQUIRED_FIELD: Description missing")

    amount_abs = abs(signed_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    transaction_type = "debit" if signed_amount < 0 else "credit"
    hash_value = compute_hash(parsed_date, description, amount_abs)

    return ParsedRow(
        date_value=parsed_date,
        description=description,
        amount=amount_abs,
        transaction_type=transaction_type,
        hash_value=hash_value,
        raw_data=raw_data,
    )


def parse_csv_bytes(raw_bytes: bytes, original_filename: str) -> ParseResult:
    errors: list[ParseErrorItem] = []
    parsed_rows: list[ParsedRow] = []

    text = decode_text(raw_bytes)
    delimiter = detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    try:
        headers = next(reader)
    except StopIteration:
        return ParseResult(rows=[], errors=[])

    roles = detect_column_roles(headers)
    attempted = 0

    for row_number, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue

        attempted += 1
        raw_data = row_to_raw_string(row, delimiter)

        def cell_at(index: int | None) -> str:
            if index is None or index >= len(row):
                return ""
            return row[index].strip()

        try:
            parsed = build_parsed_row(
                date_raw=cell_at(roles.get("date")),
                description_raw=cell_at(roles.get("description")),
                amount_raw=cell_at(roles.get("amount")),
                credit_raw=cell_at(roles.get("credit")) if "credit" in roles else None,
                debit_raw=cell_at(roles.get("debit")) if "debit" in roles else None,
                raw_data=raw_data,
            )
            parsed_rows.append(parsed)
        except ValueError as exc:
            message = str(exc)
            error_type = "MISSING_REQUIRED_FIELD"
            if message.startswith("INVALID_DATE"):
                error_type = "INVALID_DATE"
                message = message.replace("INVALID_DATE: ", "", 1)
            elif message.startswith("INVALID_AMOUNT"):
                error_type = "INVALID_AMOUNT"
                message = message.replace("INVALID_AMOUNT: ", "", 1)
            elif message.startswith("MISSING_REQUIRED_FIELD"):
                error_type = "MISSING_REQUIRED_FIELD"
                message = message.replace("MISSING_REQUIRED_FIELD: ", "", 1)

            errors.append(
                ParseErrorItem(
                    row_number=row_number,
                    raw_data=raw_data,
                    error_type=error_type,
                    error_message=message,
                )
            )

    if attempted > 0 and len(parsed_rows) == 0:
        return ParseResult(rows=[], errors=errors)

    return ParseResult(rows=parsed_rows, errors=errors)


def try_parse_pdf_table(
    table: list[list[Any]], source_label: str
) -> tuple[list[ParsedRow], list[ParseErrorItem]]:
    rows: list[ParsedRow] = []
    errors: list[ParseErrorItem] = []

    normalized_table = [
        [normalize_spaces("" if cell is None else str(cell)) for cell in row]
        for row in table
        if row
    ]
    if not normalized_table:
        return rows, errors

    header = normalized_table[0]
    data_rows = normalized_table[1:]

    mapped = False
    try:
        roles = detect_column_roles(header)
        mapped = True
    except HTTPException:
        roles = {}

    for index, row in enumerate(data_rows, start=2):
        if not any(cell.strip() for cell in row):
            continue

        raw_data = json.dumps(row, ensure_ascii=False)

        try:
            if mapped:

                def cell_at(role: str) -> str:
                    idx = roles.get(role)
                    if idx is None or idx >= len(row):
                        return ""
                    return row[idx]

                parsed = build_parsed_row(
                    date_raw=cell_at("date"),
                    description_raw=cell_at("description"),
                    amount_raw=cell_at("amount"),
                    credit_raw=cell_at("credit") if "credit" in roles else None,
                    debit_raw=cell_at("debit") if "debit" in roles else None,
                    raw_data=raw_data,
                )
            else:
                if len(row) < 3:
                    raise ValueError("MISSING_REQUIRED_FIELD: Not enough columns")
                parsed = build_parsed_row(
                    date_raw=row[0],
                    description_raw=row[1],
                    amount_raw=row[2],
                    raw_data=raw_data,
                )
            rows.append(parsed)
        except ValueError as exc:
            message = str(exc)
            error_type = "MISSING_REQUIRED_FIELD"
            if message.startswith("INVALID_DATE"):
                error_type = "INVALID_DATE"
                message = message.replace("INVALID_DATE: ", "", 1)
            elif message.startswith("INVALID_AMOUNT"):
                error_type = "INVALID_AMOUNT"
                message = message.replace("INVALID_AMOUNT: ", "", 1)
            elif message.startswith("MISSING_REQUIRED_FIELD"):
                error_type = "MISSING_REQUIRED_FIELD"
                message = message.replace("MISSING_REQUIRED_FIELD: ", "", 1)

            errors.append(
                ParseErrorItem(
                    row_number=index,
                    raw_data=raw_data,
                    error_type=error_type,
                    error_message=message,
                )
            )

    return rows, errors


def parse_pdf_file(file_path: Path) -> ParseResult:
    if pdfplumber is None:
        return ParseResult(
            rows=[],
            errors=[],
            fatal=True,
            fatal_code="PDF_EXTRACTION_FAILED",
            fatal_message="PDF extraction library is not available.",
        )

    parsed_rows: list[ParsedRow] = []
    errors: list[ParseErrorItem] = []
    attempted = 0

    try:
        with pdfplumber.open(str(file_path)) as pdf:
            table_rows_found = False

            for page_index, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                for table_index, table in enumerate(tables, start=1):
                    rows, table_errors = try_parse_pdf_table(
                        table, f"page_{page_index}_table_{table_index}"
                    )
                    if rows or table_errors:
                        table_rows_found = True
                        attempted += len(rows) + len(table_errors)
                        parsed_rows.extend(rows)
                        errors.extend(table_errors)

                if table_rows_found:
                    continue

                text = page.extract_text() or ""
                for line_number, line in enumerate(text.splitlines(), start=1):
                    stripped = normalize_spaces(line)
                    if not stripped:
                        continue

                    match = PDF_LINE_PATTERN.match(stripped)
                    if not match:
                        attempted += 1
                        errors.append(
                            ParseErrorItem(
                                row_number=line_number,
                                raw_data=stripped,
                                error_type="PDF_EXTRACTION_FAILED",
                                error_message="Could not parse PDF line.",
                            )
                        )
                        continue

                    attempted += 1
                    try:
                        parsed = build_parsed_row(
                            date_raw=match.group("date"),
                            description_raw=match.group("description"),
                            amount_raw=match.group("amount"),
                            raw_data=stripped,
                        )
                        parsed_rows.append(parsed)
                    except ValueError as exc:
                        message = str(exc)
                        error_type = "MISSING_REQUIRED_FIELD"
                        if message.startswith("INVALID_DATE"):
                            error_type = "INVALID_DATE"
                            message = message.replace("INVALID_DATE: ", "", 1)
                        elif message.startswith("INVALID_AMOUNT"):
                            error_type = "INVALID_AMOUNT"
                            message = message.replace("INVALID_AMOUNT: ", "", 1)
                        elif message.startswith("MISSING_REQUIRED_FIELD"):
                            error_type = "MISSING_REQUIRED_FIELD"
                            message = message.replace("MISSING_REQUIRED_FIELD: ", "", 1)

                        errors.append(
                            ParseErrorItem(
                                row_number=line_number,
                                raw_data=stripped,
                                error_type=error_type,
                                error_message=message,
                            )
                        )

    except Exception as exc:
        return ParseResult(
            rows=[],
            errors=[],
            fatal=True,
            fatal_code="PDF_EXTRACTION_FAILED",
            fatal_message=f"PDF extraction failed: {exc}",
        )

    if attempted > 0 and len(parsed_rows) == 0:
        return ParseResult(
            rows=[],
            errors=errors,
            fatal=True,
            fatal_code="PDF_EXTRACTION_FAILED",
            fatal_message="No table data detected in file.",
        )

    if attempted > 0:
        success_ratio = len(parsed_rows) / attempted if attempted else 0
        if success_ratio < 0.7:
            return ParseResult(
                rows=parsed_rows,
                errors=errors,
                fatal=True,
                fatal_code="PDF_EXTRACTION_FAILED",
                fatal_message="PDF extraction rate below 70 percent.",
            )

    return ParseResult(rows=parsed_rows, errors=errors)


def parse_csv_file(raw_bytes: bytes, original_filename: str) -> ParseResult:
    try:
        return parse_csv_bytes(raw_bytes, original_filename)
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            return ParseResult(
                rows=[],
                errors=[],
                fatal=True,
                fatal_code=exc.detail.get("code", "COLUMN_MAPPING_FAILED"),
                fatal_message=exc.detail.get("message", "CSV parsing failed."),
            )
        return ParseResult(
            rows=[],
            errors=[],
            fatal=True,
            fatal_code="COLUMN_MAPPING_FAILED",
            fatal_message="CSV parsing failed.",
        )
    except Exception as exc:
        return ParseResult(
            rows=[],
            errors=[],
            fatal=True,
            fatal_code="COLUMN_MAPPING_FAILED",
            fatal_message=str(exc),
        )


def write_file_bytes(destination: Path, data: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def insert_transaction(
    session: Session, row: ParsedRow, file_row: ImportFile, account_id: str | None
) -> bool:
    transaction = Transaction(
        import_file_id=file_row.id,
        account_id=account_id,
        date=row.date_value,
        description=row.description,
        amount=row.amount,
        type=row.transaction_type,
        category_id=None,
        hash=row.hash_value,
        raw_data=row.raw_data,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    try:
        with session.begin_nested():
            session.add(transaction)
            session.flush()
        return True
    except IntegrityError:
        return False


def process_file_record(batch_id: str, file_id: str) -> None:
    session = SessionLocal()
    try:
        batch = session.get(ImportBatch, batch_id)
        file_row = session.get(ImportFile, file_id)

        if batch is None or file_row is None:
            return

        file_row.status = "processing"
        file_row.started_at = utc_now()
        file_row.updated_at = utc_now()
        session.commit()

        raw_bytes = Path(file_row.stored_path).read_bytes()

        if file_row.mime_type == ALLOWED_MIME_TYPES["csv"]:
            parsed = parse_csv_file(raw_bytes, file_row.original_filename)
        elif file_row.mime_type == ALLOWED_MIME_TYPES["pdf"]:
            parsed = parse_pdf_file(Path(file_row.stored_path))
        else:
            parsed = ParseResult(
                rows=[],
                errors=[],
                fatal=True,
                fatal_code="INVALID_FILE_FORMAT",
                fatal_message="Only CSV and PDF files are accepted.",
            )

        new_count = 0
        duplicate_count = 0

        for error_item in parsed.errors:
            session.add(
                ImportErrorModel(
                    id=str(uuid4()),
                    file_id=file_row.id,
                    row_number=error_item.row_number,
                    raw_data=error_item.raw_data,
                    error_type=error_item.error_type,
                    error_message=error_item.error_message,
                    created_at=utc_now(),
                )
            )

        if parsed.fatal:
            file_row.rows_extracted = len(parsed.rows)
            file_row.rows_failed = len(parsed.errors)
            file_row.status = "failed"
            file_row.error_message = (
                f"{parsed.fatal_code}: {parsed.fatal_message}"
                if parsed.fatal_code
                else parsed.fatal_message
            )
            file_row.completed_at = utc_now()
            file_row.updated_at = utc_now()
            session.commit()
        else:
            existing_hashes = set()
            if parsed.rows:
                existing_rows = session.execute(
                    select(Transaction.hash).where(
                        Transaction.hash.in_([row.hash_value for row in parsed.rows])
                    )
                ).all()
                existing_hashes = {row[0] for row in existing_rows}

            for row in parsed.rows:
                if row.hash_value in existing_hashes:
                    duplicate_count += 1
                    continue

                if insert_transaction(session, row, file_row, batch.account_id):
                    new_count += 1
                else:
                    duplicate_count += 1

            file_row.rows_extracted = len(parsed.rows)
            file_row.rows_failed = len(parsed.errors)

            if len(parsed.rows) == 0:
                file_row.status = "failed"
                file_row.error_message = "No transactions extracted."
            else:
                file_row.status = "completed"
                file_row.error_message = None

            file_row.completed_at = utc_now()
            file_row.updated_at = utc_now()
            session.commit()

        batch.total_created = int((batch.total_created or 0) + new_count)
        batch.total_skipped = int((batch.total_skipped or 0) + duplicate_count)

        batch_files = (
            session.execute(select(ImportFile).where(ImportFile.batch_id == batch_id))
            .scalars()
            .all()
        )

        has_open_files = any(
            current_file.status in {"queued", "processing"}
            for current_file in batch_files
        )
        if has_open_files:
            batch.status = "processing"
        else:
            failed_files = sum(
                1 for current_file in batch_files if current_file.status == "failed"
            )
            has_file_errors = any(
                current_file.rows_failed > 0 or current_file.error_message
                for current_file in batch_files
            )

            if failed_files == len(batch_files) and len(batch_files) > 0:
                batch.status = "failed"
            elif failed_files > 0 or has_file_errors:
                batch.status = "partial_failure"
            else:
                batch.status = "completed"

        batch.updated_at = utc_now()
        session.commit()

    except Exception as exc:
        session.rollback()
        batch = session.get(ImportBatch, batch_id)
        file_row = session.get(ImportFile, file_id)
        if file_row is not None:
            file_row.status = "failed"
            file_row.error_message = str(exc)
            file_row.completed_at = utc_now()
            file_row.updated_at = utc_now()
        if batch is not None:
            batch.status = "partial_failure"
            batch.updated_at = utc_now()
        session.commit()
    finally:
        session.close()


@app.post("/api/v1/ingestion/upload", status_code=202)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    account_id: str | None = Form(None),
):
    if not files:
        raise_api_error(
            400, "NO_FILES_PROVIDED", "No files were included in the upload."
        )
    if len(files) > MAX_FILES_PER_REQUEST:
        raise_api_error(400, "TOO_MANY_FILES", "Maximum 20 files per upload.")

    account_id = sanitize_uuid(account_id, "account_id")

    prepared_files: list[dict[str, Any]] = []

    for upload in files:
        raw_bytes = await upload.read()
        size_bytes = len(raw_bytes)

        if size_bytes == 0:
            raise_api_error(422, "EMPTY_FILE", "The file is empty.")
        if size_bytes > MAX_FILE_SIZE_BYTES:
            raise_api_error(400, "FILE_TOO_LARGE", "File exceeds the 10 MB size limit.")

        file_type = detect_file_type(raw_bytes)
        mime_type = ALLOWED_MIME_TYPES[file_type]

        prepared_files.append(
            {
                "upload": upload,
                "raw_bytes": raw_bytes,
                "size_bytes": size_bytes,
                "file_type": file_type,
                "mime_type": mime_type,
            }
        )

    batch_id = ""
    response_files: list[dict[str, Any]] = []

    session = SessionLocal()
    try:
        batch_id = str(uuid4())
        batch = ImportBatch(
            id=batch_id,
            account_id=account_id,
            status="processing",
            file_count=len(prepared_files),
            total_created=0,
            total_skipped=0,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(batch)

        for item in prepared_files:
            file_id = str(uuid4())
            stored_path = file_path_for(batch_id, file_id, item["mime_type"])
            write_file_bytes(stored_path, item["raw_bytes"])

            file_row = ImportFile(
                id=file_id,
                batch_id=batch_id,
                original_filename=item["upload"].filename or "unknown",
                stored_path=str(stored_path),
                mime_type=item["mime_type"],
                size_bytes=item["size_bytes"],
                status="queued",
                rows_extracted=0,
                rows_failed=0,
                error_message=None,
                started_at=None,
                completed_at=None,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(file_row)

            response_files.append(
                {
                    "file_id": file_id,
                    "original_filename": file_row.original_filename,
                    "mime_type": file_row.mime_type,
                    "size_bytes": file_row.size_bytes,
                    "status": file_row.status,
                }
            )

        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise_api_error(500, "UPLOAD_FAILED", str(exc))
    finally:
        session.close()

    for file_record in response_files:
        background_tasks.add_task(process_file_record, batch_id, file_record["file_id"])

    return {
        "batch_id": batch_id,
        "status": "processing",
        "files": response_files,
    }


@app.get("/api/v1/ingestion/batches/{batch_id}")
def get_batch_status(batch_id: str):
    session = SessionLocal()
    try:
        batch = session.get(ImportBatch, batch_id)
        if batch is None:
            raise_api_error(404, "BATCH_NOT_FOUND", "Import batch not found.")

        assert batch is not None

        files = (
            session.execute(
                select(ImportFile)
                .where(ImportFile.batch_id == batch_id)
                .order_by(ImportFile.created_at.asc())
            )
            .scalars()
            .all()
        )
        payload = serialize_batch(batch, files)
        return payload
    finally:
        session.close()


@app.get("/api/v1/ingestion/batches/{batch_id}/errors")
def get_batch_errors(
    batch_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
):
    session = SessionLocal()
    try:
        batch = session.get(ImportBatch, batch_id)
        if batch is None:
            raise_api_error(404, "BATCH_NOT_FOUND", "Import batch not found.")

        assert batch is not None

        total = session.execute(
            select(func.count(ImportErrorModel.id)).where(
                ImportErrorModel.file_id.in_(
                    select(ImportFile.id).where(ImportFile.batch_id == batch_id)
                )
            )
        ).scalar_one()

        offset = (page - 1) * page_size
        error_rows = (
            session.execute(
                select(ImportErrorModel)
                .where(
                    ImportErrorModel.file_id.in_(
                        select(ImportFile.id).where(ImportFile.batch_id == batch_id)
                    )
                )
                .order_by(ImportErrorModel.created_at.asc())
                .offset(offset)
                .limit(page_size)
            )
            .scalars()
            .all()
        )

        file_ids = [error_row.file_id for error_row in error_rows]
        files = {}
        if file_ids:
            file_rows = (
                session.execute(select(ImportFile).where(ImportFile.id.in_(file_ids)))
                .scalars()
                .all()
            )
            files = {file_row.id: file_row for file_row in file_rows}

        error_payloads = []
        for item in error_rows:
            file_row = files.get(item.file_id)
            error_payloads.append(
                {
                    "file_id": item.file_id,
                    "original_filename": file_row.original_filename
                    if file_row
                    else None,
                    "row_number": item.row_number,
                    "raw_data": item.raw_data,
                    "error_type": item.error_type,
                    "error_message": item.error_message,
                }
            )

        return {
            "batch_id": batch.id,
            "errors": error_payloads,
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
        }
    finally:
        session.close()


@app.get("/api/v1/ingestion/batches")
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status: str | None = Query(None),
):
    if status is not None and status not in BATCH_STATUS_VALUES:
        raise_api_error(400, "INVALID_STATUS", "Invalid batch status.")

    session = SessionLocal()
    try:
        query = select(ImportBatch)
        if status is not None:
            query = query.where(ImportBatch.status == status)

        total = session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()
        offset = (page - 1) * page_size
        batches = (
            session.execute(
                query.order_by(desc(ImportBatch.created_at))
                .offset(offset)
                .limit(page_size)
            )
            .scalars()
            .all()
        )

        return {
            "batches": [serialize_batch_list(batch) for batch in batches],
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
        }
    finally:
        session.close()


@app.get("/api/v1/categories")
def list_categories(include_system: bool = True):
    session = SessionLocal()
    try:
        query = select(Category)
        if not include_system:
            query = query.where(Category.is_system.is_(False))
        rows = session.execute(query.order_by(Category.name.asc())).scalars().all()
        return {"data": [serialize_category(row) for row in rows], "total": len(rows)}
    finally:
        session.close()


@app.post("/api/v1/categories", status_code=201)
async def create_category(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(
            400,
            "INVALID_CATEGORY_NAME",
            "Category name must be between 1 and 100 characters.",
        )
    data = validate_category_payload(payload, allow_partial=False)
    name = normalize_category_name(str(data.get("name", "")))
    color = str(data.get("color", CATEGORY_COLOR_DEFAULT))
    icon = data.get("icon")

    if not (1 <= len(name) <= CATEGORY_NAME_MAX):
        raise_api_error(
            400,
            "INVALID_CATEGORY_NAME",
            "Category name must be between 1 and 100 characters.",
        )
    if color and not is_valid_hex_color(color):
        raise_api_error(
            400,
            "INVALID_COLOR_FORMAT",
            "Color must be a valid hex code (e.g., #FF5733).",
        )

    session = SessionLocal()
    try:
        existing = session.execute(
            select(Category).where(func.lower(Category.name) == name.lower())
        ).scalar_one_or_none()
        if existing is not None:
            raise_api_error(
                409,
                "CATEGORY_ALREADY_EXISTS",
                f"A category named '{name}' already exists.",
            )

        category = Category(
            name=name,
            color=color or CATEGORY_COLOR_DEFAULT,
            icon=icon,
            is_system=False,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        return serialize_category(category)
    finally:
        session.close()


@app.put("/api/v1/categories/{category_id}")
async def update_category(category_id: int, request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(
            400,
            "INVALID_CATEGORY_NAME",
            "Category name must be between 1 and 100 characters.",
        )
    data = validate_category_payload(payload, allow_partial=True)

    session = SessionLocal()
    try:
        category = get_category_or_404(session, category_id)
        if category.is_system:
            raise_api_error(
                403,
                "SYSTEM_CATEGORY_PROTECTED",
                "System categories cannot be modified or deleted.",
            )

        if "name" in data:
            name = normalize_category_name(str(data["name"]))
            if not (1 <= len(name) <= CATEGORY_NAME_MAX):
                raise_api_error(
                    400,
                    "INVALID_CATEGORY_NAME",
                    "Category name must be between 1 and 100 characters.",
                )
            existing = session.execute(
                select(Category).where(
                    func.lower(Category.name) == name.lower(),
                    Category.id != category_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise_api_error(
                    409,
                    "CATEGORY_ALREADY_EXISTS",
                    f"A category named '{name}' already exists.",
                )
            category.name = name

        if "color" in data:
            color = str(data["color"])
            if not is_valid_hex_color(color):
                raise_api_error(
                    400,
                    "INVALID_COLOR_FORMAT",
                    "Color must be a valid hex code (e.g., #FF5733).",
                )
            category.color = color

        if "icon" in data:
            category.icon = data["icon"]

        category.updated_at = utc_now()
        session.commit()
        session.refresh(category)
        return serialize_category(category)
    finally:
        session.close()


@app.delete("/api/v1/categories/{category_id}", status_code=204)
def delete_category(category_id: int):
    session = SessionLocal()
    try:
        category = get_category_or_404(session, category_id)
        if category.is_system:
            raise_api_error(
                403,
                "SYSTEM_CATEGORY_PROTECTED",
                "System categories cannot be modified or deleted.",
            )

        session.execute(
            select(Transaction).where(Transaction.category_id == category_id)
        )
        transactions = (
            session.execute(
                select(Transaction).where(Transaction.category_id == category_id)
            )
            .scalars()
            .all()
        )
        for transaction in transactions:
            transaction.category_id = None
            transaction.categorized_at = utc_now()
            transaction.updated_at = utc_now()

        rules = (
            session.execute(
                select(CategorizationRule).where(
                    CategorizationRule.category_id == category_id
                )
            )
            .scalars()
            .all()
        )
        for rule in rules:
            session.delete(rule)

        session.delete(category)
        session.commit()
        return Response(status_code=204)
    finally:
        session.close()


@app.get("/api/v1/rules")
def list_rules(
    category_id: int | None = None,
    source: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("priority"),
    sort_order: str = Query("desc"),
):
    session = SessionLocal()
    try:
        query = select(CategorizationRule)
        if category_id is not None:
            query = query.where(CategorizationRule.category_id == category_id)
        if source is not None:
            query = query.where(CategorizationRule.source == source)
        if is_active is not None:
            query = query.where(CategorizationRule.is_active.is_(is_active))
        if search:
            query = query.where(
                CategorizationRule.keyword.contains(normalize_rule_keyword(search))
            )

        sort_map = {
            "priority": CategorizationRule.priority,
            "keyword": CategorizationRule.keyword,
            "created_at": CategorizationRule.created_at,
        }
        sort_column = sort_map.get(sort_by, CategorizationRule.priority)
        if sort_order == "asc":
            query = query.order_by(sort_column.asc(), CategorizationRule.id.asc())
        else:
            query = query.order_by(sort_column.desc(), CategorizationRule.id.asc())

        total = session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()
        rows = (
            session.execute(query.offset((page - 1) * page_size).limit(page_size))
            .scalars()
            .all()
        )
        return {
            "data": [serialize_rule(session, row) for row in rows],
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
        }
    finally:
        session.close()


@app.post("/api/v1/rules", status_code=201)
async def create_rule(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(
            400, "INVALID_KEYWORD", "Keyword must be between 1 and 255 characters."
        )
    data = validate_rule_payload(payload)
    keyword = normalize_rule_keyword(str(data.get("keyword", "")))
    if not (1 <= len(keyword) <= RULE_KEYWORD_MAX):
        raise_api_error(
            400, "INVALID_KEYWORD", "Keyword must be between 1 and 255 characters."
        )
    match_type = str(data.get("match_type", "contains"))
    if match_type not in MATCH_TYPES:
        raise_api_error(
            400,
            "INVALID_MATCH_TYPE",
            "match_type must be one of: exact, contains, starts_with, ends_with.",
        )
    priority = int(data.get("priority", 50))
    if priority < 0:
        priority = 0
    category_id = data.get("category_id")

    session = SessionLocal()
    try:
        category = get_category_or_404(session, int(category_id))
        existing = session.execute(
            select(CategorizationRule).where(
                CategorizationRule.keyword == keyword,
                CategorizationRule.match_type == match_type,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise_api_error(
                409,
                "RULE_ALREADY_EXISTS",
                f"A rule with keyword '{keyword}' and match_type '{match_type}' already exists.",
            )

        rule = CategorizationRule(
            keyword=keyword,
            category_id=category.id,
            match_type=match_type,
            priority=priority,
            source="manual",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return serialize_rule(session, rule)
    finally:
        session.close()


@app.put("/api/v1/rules/{rule_id}")
async def update_rule(rule_id: int, request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(
            400, "INVALID_KEYWORD", "Keyword must be between 1 and 255 characters."
        )
    data = validate_rule_payload(payload, allow_partial=True)

    session = SessionLocal()
    try:
        rule = get_rule_or_404(session, rule_id)

        if "keyword" in data:
            keyword = normalize_rule_keyword(str(data["keyword"]))
            if not (1 <= len(keyword) <= RULE_KEYWORD_MAX):
                raise_api_error(
                    400,
                    "INVALID_KEYWORD",
                    "Keyword must be between 1 and 255 characters.",
                )
            rule.keyword = keyword

        if "match_type" in data:
            match_type = str(data["match_type"])
            if match_type not in MATCH_TYPES:
                raise_api_error(
                    400,
                    "INVALID_MATCH_TYPE",
                    "match_type must be one of: exact, contains, starts_with, ends_with.",
                )
            rule.match_type = match_type

        if "category_id" in data:
            category = get_category_or_404(session, int(data["category_id"]))
            rule.category_id = category.id

        if "priority" in data:
            rule.priority = max(0, int(data["priority"]))

        if "is_active" in data:
            rule.is_active = bool(data["is_active"])

        duplicate = session.execute(
            select(CategorizationRule).where(
                CategorizationRule.keyword == rule.keyword,
                CategorizationRule.match_type == rule.match_type,
                CategorizationRule.id != rule_id,
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise_api_error(
                409,
                "RULE_ALREADY_EXISTS",
                f"A rule with keyword '{rule.keyword}' and match_type '{rule.match_type}' already exists.",
            )

        rule.updated_at = utc_now()
        session.commit()
        session.refresh(rule)
        return serialize_rule(session, rule)
    finally:
        session.close()


@app.delete("/api/v1/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int):
    session = SessionLocal()
    try:
        rule = get_rule_or_404(session, rule_id)
        session.delete(rule)
        session.commit()
        return Response(status_code=204)
    finally:
        session.close()


@app.get("/api/v1/transactions")
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    date_from: str | None = None,
    date_to: str | None = None,
    category_id: int | None = None,
    account_id: str | None = None,
    search: str | None = None,
    sort_by: str = Query("date"),
    sort_order: str = Query("desc"),
):
    session = SessionLocal()
    try:
        query = select(Transaction)
        if date_from:
            query = query.where(Transaction.date >= parse_date(date_from))
        if date_to:
            query = query.where(Transaction.date <= parse_date(date_to))
        if category_id is not None:
            if category_id == 0:
                query = query.where(Transaction.category_id.is_(None))
            else:
                query = query.where(Transaction.category_id == category_id)
        if account_id is not None:
            query = query.where(Transaction.account_id == account_id)
        if search:
            query = query.where(Transaction.description.ilike(f"%{search}%"))

        sort_map = {
            "date": Transaction.date,
            "amount": Transaction.amount,
            "description": Transaction.description,
        }
        sort_column = sort_map.get(sort_by, Transaction.date)
        if sort_order == "asc":
            query = query.order_by(sort_column.asc(), Transaction.id.asc())
        else:
            query = query.order_by(sort_column.desc(), Transaction.id.desc())

        total = session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()
        rows = (
            session.execute(query.offset((page - 1) * page_size).limit(page_size))
            .scalars()
            .all()
        )
        return {
            "items": [serialize_transaction(session, row) for row in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": int(total or 0),
                "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
            },
        }
    finally:
        session.close()


@app.get("/api/v1/transactions/{transaction_id}")
def get_transaction(transaction_id: int):
    session = SessionLocal()
    try:
        transaction = get_transaction_or_404(session, transaction_id)
        return serialize_transaction(session, transaction)
    finally:
        session.close()


@app.patch("/api/v1/transactions/{transaction_id}")
async def patch_transaction_category(transaction_id: int, request: Request):
    payload = await request.json()
    if not isinstance(payload, dict) or set(payload) - {"category_id"}:
        raise_api_error(
            400, "INVALID_CATEGORY_NAME", "Request body contains disallowed fields."
        )
    session = SessionLocal()
    try:
        transaction = get_transaction_or_404(session, transaction_id)
        category_id = payload.get("category_id")
        if category_id == "":
            raise_api_error(422, "VALIDATION_ERROR", "category_id must be null or int.")
        if category_id is None:
            apply_transaction_category(session, transaction, None, "manual")
        else:
            category = get_category_or_404(session, int(category_id))
            apply_transaction_category(session, transaction, category.id, "manual")
        session.commit()
        return serialize_transaction(session, transaction)
    finally:
        session.close()


@app.patch("/api/v1/transactions/bulk")
async def bulk_update_transaction_categories(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(
            400,
            "EMPTY_TRANSACTION_LIST",
            "transaction_ids must contain at least one ID.",
        )
    transaction_ids = validate_transaction_ids(payload.get("transaction_ids"))
    category_id = payload.get("category_id")
    session = SessionLocal()
    try:
        if category_id == "":
            raise_api_error(422, "VALIDATION_ERROR", "category_id must be null or int.")
        if category_id is not None:
            category = get_category_or_404(session, int(category_id))
            category_id = category.id

        found = (
            session.execute(
                select(Transaction).where(Transaction.id.in_(transaction_ids))
            )
            .scalars()
            .all()
        )
        found_ids = {row.id for row in found}
        missing = [tx_id for tx_id in transaction_ids if tx_id not in found_ids]
        for transaction in found:
            apply_transaction_category(session, transaction, category_id, "bulk")
        session.commit()
        response = {
            "updated_count": len(found),
            "transaction_ids": [row.id for row in found],
        }
        if missing:
            response["errors"] = [
                {"transaction_id": tx_id, "error": "TRANSACTION_NOT_FOUND"}
                for tx_id in missing
            ]
            return JSONResponse(status_code=207, content=response)
        return response
    finally:
        session.close()


@app.post("/api/v1/transactions/{transaction_id}/categorize")
async def categorize_transaction(transaction_id: int, request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(400, "VALIDATION_ERROR", "category_id required.")
    if "category_id" not in payload:
        raise_api_error(400, "VALIDATION_ERROR", "category_id required.")
    learn_rule = bool(payload.get("learn_rule", True))
    session = SessionLocal()
    try:
        transaction = get_transaction_or_404(session, transaction_id)
        category_id = payload.get("category_id")
        if category_id == "":
            raise_api_error(422, "VALIDATION_ERROR", "category_id must be null or int.")
        if category_id is None:
            apply_transaction_category(session, transaction, None, "manual")
            learned_rule = None
            category = None
        else:
            category = get_category_or_404(session, int(category_id))
            apply_transaction_category(session, transaction, category.id, "manual")
            learned_rule = (
                learn_rule_from_transaction(session, transaction, category.id)
                if learn_rule
                else None
            )
        session.commit()
        learned_rule_payload = (
            serialize_rule(session, learned_rule) if learned_rule is not None else None
        )
        return {
            "transaction_id": transaction.id,
            "category_id": category.id if category is not None else None,
            "category_name": category.name if category is not None else None,
            "categorization_source": "manual",
            "categorized_at": isoformat_z(transaction.categorized_at),
            "learned_rule": learned_rule_payload,
        }
    finally:
        session.close()


@app.post("/api/v1/transactions/categorize-bulk")
async def categorize_transactions_bulk(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(
            400,
            "EMPTY_TRANSACTION_LIST",
            "transaction_ids must contain at least one ID.",
        )
    transaction_ids = validate_transaction_ids(payload.get("transaction_ids"))
    if payload.get("category_id") == "":
        raise_api_error(422, "VALIDATION_ERROR", "category_id must be null or int.")
    category = None
    session = SessionLocal()
    try:
        category_id = payload.get("category_id")
        if category_id is not None:
            category = get_category_or_404(session, int(category_id))
        rows = (
            session.execute(
                select(Transaction).where(Transaction.id.in_(transaction_ids))
            )
            .scalars()
            .all()
        )
        for row in rows:
            apply_transaction_category(
                session, row, category.id if category else None, "bulk"
            )
        session.commit()
        return {
            "updated_count": len(rows),
            "category_id": category.id if category else None,
            "category_name": category.name if category else None,
        }
    finally:
        session.close()


@app.post("/api/v1/categorize/run")
async def run_categorization(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        payload = {}
    scope = payload.get("scope", "uncategorized")
    account_id = payload.get("account_id")
    if account_id == "":
        account_id = None

    if not _categorization_lock.acquire(blocking=False):
        raise_api_error(
            409,
            "CATEGORIZATION_IN_PROGRESS",
            "A categorization run is already in progress.",
        )

    session = SessionLocal()
    try:
        summary = categorize_transactions(session, scope=scope, account_id=account_id)
        summary["duration_ms"] = 0
        return summary
    finally:
        session.close()
        _categorization_lock.release()


@app.get("/health")
def health_check():
    return {"status": "ok"}
