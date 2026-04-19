from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import threading
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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
    inspect,
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


def serialize_account(account: "Account") -> dict[str, Any]:
    return {
        "id": account.id,
        "name": account.name,
        "created_at": isoformat_z(account.created_at),
        "updated_at": isoformat_z(account.updated_at),
    }


def extract_original_description(transaction: "Transaction") -> str:
    raw_data = transaction.raw_data
    if isinstance(raw_data, dict):
        for key in (
            "original_description",
            "description_original",
            "raw_description",
            "description",
        ):
            value = raw_data.get(key)
            if isinstance(value, str) and normalize_spaces(value):
                return normalize_spaces(value)[:500]
    return transaction.description


def resolve_account_name(session: Session, account_id: str | None) -> str | None:
    if not account_id:
        return None

    account = session.get(Account, str(account_id))
    if account is not None:
        return account.name

    return str(account_id)


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
    import_id = file_row.batch_id if file_row else transaction.import_file_id

    amount = Decimal(str(transaction.amount or 0))
    if transaction.type == "debit":
        amount = -abs(amount)
    else:
        amount = abs(amount)

    return {
        "id": transaction.id,
        "date": transaction.date.isoformat(),
        "description": transaction.description,
        "original_description": extract_original_description(transaction),
        "amount": float(amount),
        "category_id": transaction.category_id,
        "category_name": category.name if category else None,
        "account_id": transaction.account_id,
        "account_name": resolve_account_name(session, transaction.account_id),
        "import_id": import_id,
        "categorization_source": transaction.categorization_source,
        "categorized_at": isoformat_z(transaction.categorized_at),
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
                "DUPLICATE_IDS",
                "transaction_ids must contain unique IDs.",
            )
        seen.add(item)
        ids.append(item)
    return ids


def get_category_or_422(session: Session, category_id: int) -> "Category":
    category = session.get(Category, category_id)
    if category is None:
        raise_api_error(
            422, "CATEGORY_NOT_FOUND", f"Category with id {category_id} does not exist."
        )
    return category


def parse_optional_transaction_category_id(session: Session, value: Any) -> int | None:
    if value == "":
        raise_api_error(422, "VALIDATION_ERROR", "category_id must be null or int.")
    if value is None:
        return None
    if isinstance(value, bool):
        raise_api_error(422, "VALIDATION_ERROR", "category_id must be null or int.")
    try:
        category_id = int(value)
    except Exception:
        raise_api_error(422, "VALIDATION_ERROR", "category_id must be null or int.")
    return get_category_or_422(session, category_id).id


def parse_transaction_dates(
    date_from: str | None, date_to: str | None
) -> tuple[date | None, date | None]:
    parsed_from = None
    parsed_to = None

    if date_from:
        try:
            parsed_from = parse_date(date_from)
        except ValueError:
            raise_api_error(
                400, "VALIDATION_ERROR", "Invalid date_from. Expected YYYY-MM-DD."
            )

    if date_to:
        try:
            parsed_to = parse_date(date_to)
        except ValueError:
            raise_api_error(
                400, "VALIDATION_ERROR", "Invalid date_to. Expected YYYY-MM-DD."
            )

    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise_api_error(400, "INVALID_DATE_RANGE", "date_from cannot be after date_to.")

    return parsed_from, parsed_to


def validate_transaction_sort(sort_by: str, sort_order: str) -> tuple[str, str]:
    allowed_sort_by = {"date", "amount", "description"}
    allowed_sort_order = {"asc", "desc"}

    if sort_by not in allowed_sort_by:
        raise_api_error(
            400,
            "INVALID_SORT_FIELD",
            "sort_by must be one of: date, amount, description.",
        )
    if sort_order not in allowed_sort_order:
        raise_api_error(400, "VALIDATION_ERROR", "sort_order must be asc or desc.")

    return sort_by, sort_order


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


def ensure_account(
    session: Session, account_id: str | None, name: str | None = None
) -> "Account" | None:
    if account_id is None:
        return None

    normalized_id = normalize_spaces(str(account_id))
    if not normalized_id:
        return None

    normalized_name = normalize_spaces(name or normalized_id)[:100] or normalized_id
    account = session.get(Account, normalized_id)

    if account is None:
        account = Account(
            id=normalized_id,
            name=normalized_name,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(account)
        session.flush()
        return account

    if normalized_name and account.name != normalized_name:
        account.name = normalized_name
        account.updated_at = utc_now()

    return account


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


def record_transaction_category_change(
    session: Session,
    transaction: "Transaction",
    old_category_id: int | None,
    new_category_id: int | None,
) -> None:
    session.add(
        TransactionAuditLog(
            transaction_id=transaction.id,
            old_category_id=old_category_id,
            new_category_id=new_category_id,
            changed_at=utc_now(),
        )
    )


def apply_transaction_category(
    session: Session,
    transaction: "Transaction",
    category_id: int | None,
    source: str,
    force_metadata: bool = False,
) -> bool:
    old_category_id = transaction.category_id
    changed = old_category_id != category_id

    if not changed and not force_metadata:
        return False

    if changed:
        record_transaction_category_change(
            session, transaction, old_category_id, category_id
        )

    transaction.category_id = category_id
    if source:
        transaction.categorization_source = source
    if changed or force_metadata:
        now = utc_now()
        transaction.categorized_at = now
        transaction.updated_at = now

    return changed


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
            apply_transaction_category(
                session, transaction, matched_rule.category_id, "auto"
            )
            categorized += 1
        else:
            apply_transaction_category(session, transaction, None, "auto")
            uncategorized += 1

    session.commit()
    return {
        "processed": processed,
        "categorized": categorized,
        "uncategorized": uncategorized,
    }


FIXED_EXPENSE_FREQUENCIES = {
    "weekly",
    "biweekly",
    "monthly",
    "bimonthly",
    "quarterly",
    "semiannual",
    "annual",
}
FIXED_EXPENSE_MONTH_INTERVALS = {
    "monthly": 1,
    "bimonthly": 2,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}
FIXED_EXPENSE_ENTRY_STATUSES = {"pending", "paid", "skipped", "cancelled"}


def decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(normalized, "f")


def serialize_fixed_expense(
    session: Session, expense: "FixedExpense"
) -> dict[str, Any]:
    category = (
        session.get(Category, expense.category_id) if expense.category_id else None
    )
    account = session.get(Account, expense.account_id) if expense.account_id else None
    return {
        "id": expense.id,
        "account_id": expense.account_id,
        "account_name": account.name if account else expense.account_id,
        "category_id": expense.category_id,
        "category_name": category.name if category else None,
        "name": expense.name,
        "description": expense.description,
        "amount": decimal_to_string(expense.amount),
        "frequency": expense.frequency,
        "day_of_month": expense.day_of_month,
        "day_of_week": expense.day_of_week,
        "start_date": expense.start_date.isoformat(),
        "end_date": expense.end_date.isoformat() if expense.end_date else None,
        "is_active": expense.is_active,
        "created_at": isoformat_z(expense.created_at),
        "updated_at": isoformat_z(expense.updated_at),
    }


def serialize_fixed_expense_entry(
    session: Session, entry: "FixedExpenseEntry"
) -> dict[str, Any]:
    transaction = (
        session.get(Transaction, entry.transaction_id) if entry.transaction_id else None
    )
    return {
        "id": entry.id,
        "fixed_expense_id": entry.fixed_expense_id,
        "reference_date": entry.reference_date.isoformat(),
        "due_date": entry.due_date.isoformat(),
        "amount": decimal_to_string(entry.amount),
        "transaction_id": entry.transaction_id,
        "transaction": serialize_transaction(session, transaction)
        if transaction
        else None,
        "status": entry.status,
        "created_at": isoformat_z(entry.created_at),
        "updated_at": isoformat_z(entry.updated_at),
    }


def get_fixed_expense_or_404(session: Session, expense_id: str) -> "FixedExpense":
    expense = session.get(FixedExpense, str(expense_id))
    if expense is None:
        raise_api_error(404, "NOT_FOUND", f"Fixed expense {expense_id} not found")
    return expense


def get_fixed_expense_entry_or_404(
    session: Session, entry_id: str
) -> "FixedExpenseEntry":
    entry = session.get(FixedExpenseEntry, str(entry_id))
    if entry is None:
        raise_api_error(404, "NOT_FOUND", f"Fixed expense entry {entry_id} not found")
    return entry


def parse_fixed_expense_amount(value: Any, field_name: str = "amount") -> Decimal:
    if value in (None, ""):
        raise_api_error(400, "VALIDATION_ERROR", f"{field_name} is required.")
    if isinstance(value, bool):
        raise_api_error(400, "VALIDATION_ERROR", f"{field_name} must be a decimal.")
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        raise_api_error(400, "VALIDATION_ERROR", f"{field_name} must be a decimal.")
    if amount <= 0:
        raise_api_error(
            400, "VALIDATION_ERROR", f"{field_name} must be greater than 0."
        )
    return amount


def parse_iso_date_field(
    value: Any, field_name: str, required: bool = True
) -> date | None:
    if value in (None, ""):
        if required:
            raise_api_error(400, "VALIDATION_ERROR", f"{field_name} is required.")
        return None
    if not isinstance(value, str):
        raise_api_error(400, "VALIDATION_ERROR", f"{field_name} must use YYYY-MM-DD.")
    try:
        return datetime.strptime(normalize_spaces(value), "%Y-%m-%d").date()
    except ValueError:
        raise_api_error(400, "VALIDATION_ERROR", f"{field_name} must use YYYY-MM-DD.")


def parse_optional_int_field(
    value: Any, field_name: str, min_value: int, max_value: int
) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise_api_error(422, "VALIDATION_ERROR", f"{field_name} must be an integer.")
    try:
        parsed = int(value)
    except Exception:
        raise_api_error(422, "VALIDATION_ERROR", f"{field_name} must be an integer.")
    if parsed < min_value or parsed > max_value:
        raise_api_error(
            422,
            "VALIDATION_ERROR",
            f"{field_name} must be between {min_value} and {max_value}.",
        )
    return parsed


def normalize_fixed_expense_name(value: Any) -> str:
    if not isinstance(value, str):
        raise_api_error(400, "VALIDATION_ERROR", "name must be text.")
    normalized = normalize_spaces(value)
    if not normalized or len(normalized) > 255:
        raise_api_error(400, "VALIDATION_ERROR", "name must be 1-255 characters.")
    return normalized


def validate_fixed_expense_payload(
    session: Session,
    payload: dict[str, Any],
    partial: bool = False,
    existing: "FixedExpense" | None = None,
) -> dict[str, Any]:
    allowed = {
        "account_id",
        "category_id",
        "name",
        "description",
        "amount",
        "frequency",
        "day_of_month",
        "day_of_week",
        "start_date",
        "end_date",
        "is_active",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise_api_error(400, "VALIDATION_ERROR", "Unexpected fields in request.")

    if partial and ("account_id" in payload or "start_date" in payload):
        raise_api_error(
            400,
            "VALIDATION_ERROR",
            "account_id and start_date are immutable after creation.",
        )

    data: dict[str, Any] = {}

    if not partial or "account_id" in payload:
        raw_account_id = payload.get("account_id")
        if raw_account_id in (None, ""):
            raise_api_error(400, "VALIDATION_ERROR", "account_id is required.")
        if not isinstance(raw_account_id, str):
            raise_api_error(400, "VALIDATION_ERROR", "account_id must be text.")
        normalized_account_id = normalize_spaces(raw_account_id)
        if not normalized_account_id:
            raise_api_error(400, "VALIDATION_ERROR", "account_id is required.")
        data["account_id"] = normalized_account_id

    if not partial or "category_id" in payload:
        raw_category_id = payload.get("category_id")
        if raw_category_id in (None, ""):
            data["category_id"] = None
        else:
            if isinstance(raw_category_id, bool):
                raise_api_error(
                    422, "VALIDATION_ERROR", "category_id must be null or int."
                )
            try:
                category_id = int(raw_category_id)
            except Exception:
                raise_api_error(
                    422, "VALIDATION_ERROR", "category_id must be null or int."
                )
            data["category_id"] = get_category_or_422(session, category_id).id

    if not partial or "name" in payload:
        data["name"] = normalize_fixed_expense_name(payload.get("name"))

    if not partial or "description" in payload:
        raw_description = payload.get("description")
        if raw_description is None:
            data["description"] = None
        else:
            if not isinstance(raw_description, str):
                raise_api_error(400, "VALIDATION_ERROR", "description must be text.")
            normalized_description = normalize_spaces(raw_description)
            data["description"] = normalized_description or None

    if not partial or "amount" in payload:
        data["amount"] = parse_fixed_expense_amount(payload.get("amount"))

    if not partial or "frequency" in payload:
        raw_frequency = payload.get("frequency")
        if not isinstance(raw_frequency, str):
            raise_api_error(400, "INVALID_FREQUENCY", "frequency is required.")
        frequency = normalize_spaces(raw_frequency).lower()
        if frequency not in FIXED_EXPENSE_FREQUENCIES:
            raise_api_error(
                400, "INVALID_FREQUENCY", f"Unsupported frequency: {raw_frequency}"
            )
        data["frequency"] = frequency

    if not partial or "day_of_month" in payload:
        data["day_of_month"] = parse_optional_int_field(
            payload.get("day_of_month"), "day_of_month", 1, 31
        )

    if not partial or "day_of_week" in payload:
        data["day_of_week"] = parse_optional_int_field(
            payload.get("day_of_week"), "day_of_week", 0, 6
        )

    if not partial or "start_date" in payload:
        data["start_date"] = parse_iso_date_field(
            payload.get("start_date"), "start_date", required=True
        )

    if not partial or "end_date" in payload:
        data["end_date"] = parse_iso_date_field(
            payload.get("end_date"), "end_date", required=False
        )

    if "is_active" in payload:
        if not isinstance(payload.get("is_active"), bool):
            raise_api_error(422, "VALIDATION_ERROR", "is_active must be true or false.")
        data["is_active"] = payload["is_active"]
    elif not partial:
        data["is_active"] = True

    effective_frequency = data.get(
        "frequency", existing.frequency if existing else None
    )
    effective_day_of_month = data.get(
        "day_of_month", existing.day_of_month if existing else None
    )
    effective_day_of_week = data.get(
        "day_of_week", existing.day_of_week if existing else None
    )
    effective_start_date = data.get(
        "start_date", existing.start_date if existing else None
    )
    effective_end_date = data.get("end_date", existing.end_date if existing else None)

    if effective_end_date is not None and effective_start_date is not None:
        if effective_end_date < effective_start_date:
            raise_api_error(
                400,
                "INVALID_DATE_RANGE",
                "end_date must be on or after start_date",
            )

    if effective_frequency in {"weekly", "biweekly"}:
        if effective_day_of_week is None:
            raise_api_error(
                400,
                "INVALID_DAY_CONFIG",
                "Weekly/biweekly requires day_of_week; others require day_of_month",
            )
        data["day_of_month"] = None
    else:
        if effective_day_of_month is None:
            raise_api_error(
                400,
                "INVALID_DAY_CONFIG",
                "Weekly/biweekly requires day_of_week; others require day_of_month",
            )
        data["day_of_week"] = None

    return data


def clamp_day_of_month(year: int, month: int, day: int) -> int:
    return min(day, monthrange(year, month)[1])


def month_delta(start: date, target: date) -> int:
    return (target.year - start.year) * 12 + (target.month - start.month)


def compute_due_dates(expense: "FixedExpense", target_date: date) -> list[date]:
    if expense.frequency in {"weekly", "biweekly"}:
        current = date(target_date.year, target_date.month, 1)
        results: list[date] = []
        while current.month == target_date.month:
            if current.weekday() == expense.day_of_week:
                if expense.frequency == "weekly":
                    results.append(current)
                else:
                    delta_days = (current - expense.start_date).days
                    if delta_days >= 0 and delta_days % 14 == 0:
                        results.append(current)
            current += timedelta(days=1)
        return results

    interval = FIXED_EXPENSE_MONTH_INTERVALS[expense.frequency]
    delta_months = month_delta(expense.start_date, target_date)
    if delta_months < 0 or delta_months % interval != 0:
        return []

    due_day = clamp_day_of_month(
        target_date.year,
        target_date.month,
        expense.day_of_month or expense.start_date.day,
    )
    return [date(target_date.year, target_date.month, due_day)]


def compute_generation_hash(fixed_expense_id: str, reference_date: str) -> str:
    return hashlib.sha256(
        f"{fixed_expense_id}:{reference_date}".encode("utf-8")
    ).hexdigest()


def generate_fixed_expense_entries(
    session: Session,
    target_date: date,
    fixed_expense_id: str | None = None,
) -> dict[str, Any]:
    query = select(FixedExpense).where(FixedExpense.is_active.is_(True))
    if fixed_expense_id:
        query = query.where(FixedExpense.id == str(fixed_expense_id))

    expenses = (
        session.execute(
            query.order_by(FixedExpense.created_at.asc(), FixedExpense.id.asc())
        )
        .scalars()
        .all()
    )

    if fixed_expense_id and not expenses:
        raise_api_error(404, "NOT_FOUND", f"Fixed expense {fixed_expense_id} not found")

    generated = 0
    skipped = 0
    errors: list[dict[str, Any]] = []

    for expense in expenses:
        try:
            for due_date in compute_due_dates(expense, target_date):
                if due_date < expense.start_date:
                    continue
                if expense.end_date is not None and due_date > expense.end_date:
                    continue

                reference_date = due_date.isoformat()
                generation_hash = compute_generation_hash(expense.id, reference_date)

                existing_entry = session.execute(
                    select(FixedExpenseEntry.id).where(
                        FixedExpenseEntry.generation_hash == generation_hash
                    )
                ).scalar_one_or_none()
                if existing_entry is not None:
                    skipped += 1
                    continue

                session.add(
                    FixedExpenseEntry(
                        id=str(uuid4()),
                        fixed_expense_id=expense.id,
                        reference_date=due_date,
                        due_date=due_date,
                        amount=expense.amount,
                        transaction_id=None,
                        status="pending",
                        generation_hash=generation_hash,
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                )
                session.flush()
                generated += 1
        except HTTPException:
            raise
        except Exception as exc:
            errors.append({"fixed_expense_id": expense.id, "error": str(exc)})

    return {
        "generated_count": generated,
        "skipped_count": skipped,
        "errors": errors,
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


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    # Dashboard / credit-card billing fields (runtime-added via schema patch)
    type = Column(String(50), nullable=True)
    closing_day = Column(Integer, nullable=True)
    due_day = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True, autoincrement=True)
    import_file_id = Column(String(36), nullable=True, index=True)
    account_id = Column(String(36), nullable=True, index=True)
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


class TransactionAuditLog(Base):
    __tablename__ = "transaction_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(
        Integer,
        ForeignKey("transaction.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    new_category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    changed_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class FixedExpense(Base):
    __tablename__ = "fixed_expenses"

    id = Column(String(36), primary_key=True)
    account_id = Column(String(36), nullable=False, index=True)
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    frequency = Column(String(20), nullable=False)
    day_of_month = Column(Integer, nullable=True)
    day_of_week = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class FixedExpenseEntry(Base):
    __tablename__ = "fixed_expense_entries"

    id = Column(String(36), primary_key=True)
    fixed_expense_id = Column(
        String(36),
        ForeignKey("fixed_expenses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    transaction_id = Column(
        Integer, ForeignKey("transaction.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String(20), nullable=False, default="pending", index=True)
    generation_hash = Column(String(64), nullable=False, unique=True, index=True)
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


def ensure_account_credit_card_columns() -> None:
    # Ensure schema contains fields needed by SPEC5 dashboard credit-card logic.
    # Idempotent: only adds missing columns.
    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns("accounts")}
    except Exception:
        return

    with engine.begin() as conn:
        if "type" not in cols:
            conn.exec_driver_sql('ALTER TABLE accounts ADD COLUMN "type" VARCHAR(50)')
        if "closing_day" not in cols:
            conn.exec_driver_sql("ALTER TABLE accounts ADD COLUMN closing_day INTEGER")
        if "due_day" not in cols:
            conn.exec_driver_sql("ALTER TABLE accounts ADD COLUMN due_day INTEGER")
        if "is_active" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE accounts ADD COLUMN is_active BOOLEAN DEFAULT 1"
            )


ensure_account_credit_card_columns()

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
        ensure_account(session, account_id)
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


@app.get("/api/v1/accounts")
def list_accounts():
    session = SessionLocal()
    try:
        rows = (
            session.execute(select(Account).order_by(Account.name.asc()))
            .scalars()
            .all()
        )
        items = [serialize_account(row) for row in rows]
        seen = {item["id"] for item in items}

        transaction_account_ids = (
            session.execute(
                select(Transaction.account_id)
                .where(Transaction.account_id.is_not(None))
                .distinct()
            )
            .scalars()
            .all()
        )
        batch_account_ids = (
            session.execute(
                select(ImportBatch.account_id)
                .where(ImportBatch.account_id.is_not(None))
                .distinct()
            )
            .scalars()
            .all()
        )

        for account_id in [*transaction_account_ids, *batch_account_ids]:
            if account_id and account_id not in seen:
                items.append(
                    {
                        "id": account_id,
                        "name": account_id,
                        "created_at": None,
                        "updated_at": None,
                    }
                )
                seen.add(account_id)

        items.sort(key=lambda item: (item["name"] or item["id"]).lower())
        return {"items": items, "total": len(items)}
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
        items = [serialize_category(row) for row in rows]
        return {"items": items, "data": items, "total": len(items)}
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
    sort_by, sort_order = validate_transaction_sort(sort_by, sort_order)
    parsed_date_from, parsed_date_to = parse_transaction_dates(date_from, date_to)
    normalized_search = normalize_spaces(search) if search else None
    if normalized_search:
        normalized_search = normalized_search[:100]

    session = SessionLocal()
    try:
        query = select(Transaction)
        if parsed_date_from:
            query = query.where(Transaction.date >= parsed_date_from)
        if parsed_date_to:
            query = query.where(Transaction.date <= parsed_date_to)
        if category_id is not None:
            if category_id == 0:
                query = query.where(Transaction.category_id.is_(None))
            else:
                query = query.where(Transaction.category_id == category_id)
        if account_id not in (None, ""):
            query = query.where(Transaction.account_id == account_id)
        if normalized_search:
            query = query.where(Transaction.description.ilike(f"%{normalized_search}%"))

        sort_map = {
            "date": Transaction.date,
            "amount": Transaction.amount,
            "description": Transaction.description,
        }
        sort_column = sort_map[sort_by]
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
    if not isinstance(payload, dict):
        raise_api_error(400, "VALIDATION_ERROR", "Request body must be a JSON object.")
    if set(payload) - {"category_id"}:
        raise_api_error(
            400, "DISALLOWED_FIELDS", "Request body contains disallowed fields."
        )
    if "category_id" not in payload:
        raise_api_error(400, "VALIDATION_ERROR", "category_id is required.")

    session = SessionLocal()
    try:
        transaction = get_transaction_or_404(session, transaction_id)
        category_id = parse_optional_transaction_category_id(
            session, payload.get("category_id")
        )
        apply_transaction_category(session, transaction, category_id, "manual")
        session.commit()
        session.refresh(transaction)
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
    if "category_id" not in payload:
        raise_api_error(400, "VALIDATION_ERROR", "category_id is required.")

    transaction_ids = validate_transaction_ids(payload.get("transaction_ids"))
    session = SessionLocal()
    try:
        category_id = parse_optional_transaction_category_id(
            session, payload.get("category_id")
        )

        found_rows = (
            session.execute(
                select(Transaction).where(Transaction.id.in_(transaction_ids))
            )
            .scalars()
            .all()
        )
        found_by_id = {row.id: row for row in found_rows}

        updated_ids: list[int] = []
        errors: list[dict[str, Any]] = []

        for requested_id in transaction_ids:
            transaction = found_by_id.get(requested_id)
            if transaction is None:
                errors.append(
                    {
                        "transaction_id": requested_id,
                        "error": "TRANSACTION_NOT_FOUND",
                        "message": f"Transaction with id {requested_id} does not exist",
                    }
                )
                continue

            if apply_transaction_category(session, transaction, category_id, "bulk"):
                updated_ids.append(transaction.id)

        session.commit()

        response = {
            "updated_count": len(updated_ids),
            "transaction_ids": updated_ids,
        }
        if errors:
            response["errors"] = errors
            return JSONResponse(status_code=207, content=response)
        return response
    finally:
        session.close()


@app.post("/api/v1/fixed-expenses", status_code=201)
async def create_fixed_expense(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(400, "VALIDATION_ERROR", "Request body must be a JSON object.")

    session = SessionLocal()
    try:
        data = validate_fixed_expense_payload(session, payload, partial=False)
        ensure_account(session, data["account_id"])

        expense = FixedExpense(
            id=str(uuid4()),
            account_id=data["account_id"],
            category_id=data.get("category_id"),
            name=data["name"],
            description=data.get("description"),
            amount=data["amount"],
            frequency=data["frequency"],
            day_of_month=data.get("day_of_month"),
            day_of_week=data.get("day_of_week"),
            start_date=data["start_date"],
            end_date=data.get("end_date"),
            is_active=data.get("is_active", True),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(expense)
        session.commit()
        session.refresh(expense)
        return serialize_fixed_expense(session, expense)
    finally:
        session.close()


@app.get("/api/v1/fixed-expenses")
def list_fixed_expenses(
    account_id: str | None = None,
    is_active: bool | None = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    session = SessionLocal()
    try:
        query = select(FixedExpense)
        if account_id not in (None, ""):
            query = query.where(FixedExpense.account_id == account_id)
        if is_active is not None:
            query = query.where(FixedExpense.is_active.is_(is_active))

        total = session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()
        rows = (
            session.execute(
                query.order_by(FixedExpense.created_at.desc(), FixedExpense.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )

        return {
            "items": [serialize_fixed_expense(session, row) for row in rows],
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
        }
    finally:
        session.close()


@app.post("/api/v1/fixed-expenses/generate")
async def generate_fixed_expenses(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(400, "VALIDATION_ERROR", "Request body must be a JSON object.")

    target_date = parse_iso_date_field(payload.get("target_date"), "target_date")
    fixed_expense_id = payload.get("fixed_expense_id")
    if fixed_expense_id == "":
        fixed_expense_id = None
    if fixed_expense_id is not None:
        fixed_expense_id = normalize_spaces(str(fixed_expense_id))

    session = SessionLocal()
    try:
        result = generate_fixed_expense_entries(
            session, target_date, fixed_expense_id=fixed_expense_id
        )
        session.commit()
        return result
    finally:
        session.close()


@app.patch("/api/v1/fixed-expenses/entries/{entry_id}")
async def update_fixed_expense_entry(entry_id: str, request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(400, "VALIDATION_ERROR", "Request body must be a JSON object.")

    allowed = {"status", "transaction_id"}
    if set(payload) - allowed:
        raise_api_error(400, "VALIDATION_ERROR", "Unexpected fields in request.")

    session = SessionLocal()
    try:
        entry = get_fixed_expense_entry_or_404(session, entry_id)

        if "status" in payload:
            status = payload.get("status")
            if not isinstance(status, str):
                raise_api_error(400, "VALIDATION_ERROR", "status must be text.")
            normalized_status = normalize_spaces(status).lower()
            if normalized_status not in FIXED_EXPENSE_ENTRY_STATUSES:
                raise_api_error(400, "VALIDATION_ERROR", "Invalid status.")
            entry.status = normalized_status

        if "transaction_id" in payload:
            transaction_id = payload.get("transaction_id")
            if transaction_id == "":
                raise_api_error(
                    422, "VALIDATION_ERROR", "transaction_id must be null or int."
                )
            if transaction_id is None:
                entry.transaction_id = None
            else:
                if isinstance(transaction_id, bool):
                    raise_api_error(
                        422, "VALIDATION_ERROR", "transaction_id must be null or int."
                    )
                try:
                    parsed_transaction_id = int(transaction_id)
                except Exception:
                    raise_api_error(
                        422, "VALIDATION_ERROR", "transaction_id must be null or int."
                    )
                get_transaction_or_404(session, parsed_transaction_id)
                entry.transaction_id = parsed_transaction_id

        entry.updated_at = utc_now()
        session.commit()
        session.refresh(entry)
        return serialize_fixed_expense_entry(session, entry)
    finally:
        session.close()


@app.get("/api/v1/fixed-expenses/{expense_id}/entries")
def list_fixed_expense_entries(
    expense_id: str,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    session = SessionLocal()
    try:
        expense = get_fixed_expense_or_404(session, expense_id)
        query = select(FixedExpenseEntry).where(
            FixedExpenseEntry.fixed_expense_id == expense.id
        )

        if status:
            normalized_status = normalize_spaces(status).lower()
            if normalized_status not in FIXED_EXPENSE_ENTRY_STATUSES:
                raise_api_error(400, "VALIDATION_ERROR", "Invalid status.")
            query = query.where(FixedExpenseEntry.status == normalized_status)

        if from_date:
            query = query.where(
                FixedExpenseEntry.reference_date
                >= parse_iso_date_field(from_date, "from_date")
            )
        if to_date:
            query = query.where(
                FixedExpenseEntry.reference_date
                <= parse_iso_date_field(to_date, "to_date")
            )

        total = session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()
        rows = (
            session.execute(
                query.order_by(
                    FixedExpenseEntry.due_date.desc(), FixedExpenseEntry.id.desc()
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )

        return {
            "items": [serialize_fixed_expense_entry(session, row) for row in rows],
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
        }
    finally:
        session.close()


@app.get("/api/v1/fixed-expenses/{expense_id}")
def get_fixed_expense(expense_id: str):
    session = SessionLocal()
    try:
        expense = get_fixed_expense_or_404(session, expense_id)
        return serialize_fixed_expense(session, expense)
    finally:
        session.close()


@app.patch("/api/v1/fixed-expenses/{expense_id}")
async def update_fixed_expense(expense_id: str, request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise_api_error(400, "VALIDATION_ERROR", "Request body must be a JSON object.")

    session = SessionLocal()
    try:
        expense = get_fixed_expense_or_404(session, expense_id)
        data = validate_fixed_expense_payload(
            session, payload, partial=True, existing=expense
        )

        if "account_id" in data:
            ensure_account(session, data["account_id"])

        for field_name, value in data.items():
            setattr(expense, field_name, value)

        expense.updated_at = utc_now()
        session.commit()
        session.refresh(expense)
        return serialize_fixed_expense(session, expense)
    finally:
        session.close()


@app.delete("/api/v1/fixed-expenses/{expense_id}", status_code=204)
def delete_fixed_expense(expense_id: str):
    session = SessionLocal()
    try:
        expense = get_fixed_expense_or_404(session, expense_id)
        today = date.today()
        expense.is_active = False
        expense.end_date = today if today >= expense.start_date else expense.start_date
        expense.updated_at = utc_now()
        session.commit()
        return Response(status_code=204)
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


def _validate_month_year(month: int, year: int) -> None:
    if not (1 <= month <= 12):
        raise_api_error(
            400,
            "INVALID_MONTH",
            "month must be between 1 and 12",
        )

    current_year = date.today().year
    if not (2000 <= year <= current_year + 1):
        raise_api_error(
            400,
            "INVALID_YEAR",
            f"year must be between 2000 and {current_year + 1}",
        )


def _month_bounds(month: int, year: int) -> tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    # month: 1..12
    m0 = month - 1 + delta
    y = year + (m0 // 12)
    m = (m0 % 12) + 1
    return y, m


def _serialize_period(start: date, end: date) -> dict[str, str]:
    return {"start": start.isoformat(), "end": end.isoformat()}


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


@app.get("/api/v1/dashboard/monthly-summary")
def get_monthly_summary(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None),
):
    today = date.today()
    month_eff = month if month is not None else today.month
    year_eff = year if year is not None else today.year

    _validate_month_year(month_eff, year_eff)
    start_date, end_date = _month_bounds(month_eff, year_eff)

    session = SessionLocal()
    try:
        rows = session.execute(
            select(
                Transaction.category_id,
                Category.name.label("category_name"),
                Transaction.type,
                func.count(Transaction.id).label("transaction_count"),
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            )
            .select_from(Transaction)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(Transaction.date >= start_date, Transaction.date <= end_date)
            .where(Transaction.type.in_(["debit", "credit"]))
            .group_by(Transaction.category_id, Category.name, Transaction.type)
        ).all()

        total_expenses = Decimal("0.00")
        total_income = Decimal("0.00")

        expenses: list[dict[str, Any]] = []

        for r in rows:
            tx_type = r.type
            tx_total = r.total if r.total is not None else Decimal("0.00")
            if tx_type == "debit":
                total_expenses += tx_total
                expenses.append(
                    {
                        "category_id": r.category_id,
                        "category_name": r.category_name or "Sem Categoria",
                        "total": tx_total,
                        "transaction_count": r.transaction_count,
                    }
                )
            elif tx_type == "credit":
                total_income += tx_total

        categories: list[dict[str, Any]] = []
        expenses_sorted = sorted(expenses, key=lambda x: x["total"], reverse=True)
        for item in expenses_sorted:
            pct = (
                round((item["total"] / total_expenses) * 100, 2)
                if total_expenses > 0
                else Decimal("0.00")
            )
            categories.append(
                {
                    "category_id": item["category_id"],
                    "category_name": item["category_name"],
                    "total": _to_float(item["total"]),
                    "percentage": _to_float(pct),
                    "transaction_count": int(item["transaction_count"] or 0),
                }
            )

        net = total_income - total_expenses
        return {
            "month": month_eff,
            "year": year_eff,
            "total_expenses": _to_float(total_expenses),
            "total_income": _to_float(total_income),
            "net": _to_float(net),
            "categories": categories,
        }
    except Exception:
        raise_api_error(
            500, "AGGREGATION_FAILED", "Failed to compute dashboard aggregation"
        )
    finally:
        session.close()


@app.get("/api/v1/dashboard/charts/category-breakdown")
def get_category_breakdown(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None),
):
    today = date.today()
    month_eff = month if month is not None else today.month
    year_eff = year if year is not None else today.year

    _validate_month_year(month_eff, year_eff)
    start_date, end_date = _month_bounds(month_eff, year_eff)

    session = SessionLocal()
    try:
        rows = session.execute(
            select(
                Transaction.category_id,
                Category.name.label("category_name"),
                Category.color.label("category_color"),
                func.count(Transaction.id).label("transaction_count"),
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            )
            .select_from(Transaction)
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(Transaction.date >= start_date, Transaction.date <= end_date)
            .where(Transaction.type == "debit")
            .group_by(Transaction.category_id, Category.name, Category.color)
        ).all()

        total_expenses = sum((r.total or Decimal("0.00")) for r in rows)

        slices: list[dict[str, Any]] = []
        uncategorized_total = Decimal("0.00")

        for r in rows:
            if r.category_id is None:
                uncategorized_total += r.total or Decimal("0.00")
                continue

            color = r.category_color or "#9E9E9E"
            if not color:
                color = "#9E9E9E"

            pct = (
                round(((r.total or Decimal("0.00")) / total_expenses) * 100, 2)
                if total_expenses > 0
                else Decimal("0.00")
            )

            slices.append(
                {
                    "category_id": r.category_id,
                    "category_name": r.category_name or "Sem Categoria",
                    "total": _to_float(r.total),
                    "percentage": _to_float(pct),
                    "color": color,
                }
            )

        # Sort slices by total desc (stable for chart)
        slices = sorted(slices, key=lambda x: x["total"], reverse=True)

        uncategorized_percentage = (
            _to_float(round((uncategorized_total / total_expenses) * 100, 2))
            if total_expenses > 0
            else 0.0
        )

        return {
            "month": month_eff,
            "year": year_eff,
            "slices": slices,
            "uncategorized_total": _to_float(uncategorized_total),
            "uncategorized_percentage": uncategorized_percentage,
        }
    except Exception:
        raise_api_error(
            500, "AGGREGATION_FAILED", "Failed to compute dashboard aggregation"
        )
    finally:
        session.close()


@app.get("/api/v1/dashboard/charts/time-series")
def get_time_series(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None),
    granularity: str | None = Query("daily"),
    months_back: int | None = Query(6),
):
    today = date.today()
    month_eff = month if month is not None else today.month
    year_eff = year if year is not None else today.year

    _validate_month_year(month_eff, year_eff)

    if granularity not in ("daily", "monthly"):
        raise_api_error(
            400,
            "INVALID_GRANULARITY",
            'granularity must be "daily" or "monthly"',
        )

    months_back_eff = months_back if months_back is not None else 6
    if not (1 <= months_back_eff <= 24):
        raise_api_error(
            400,
            "INVALID_MONTHS_BACK",
            "months_back must be between 1 and 24",
        )

    session = SessionLocal()
    try:
        if granularity == "daily":
            start_date, end_date = _month_bounds(month_eff, year_eff)

            rows = session.execute(
                select(
                    Transaction.date.label("d"),
                    Transaction.type.label("t"),
                    func.coalesce(func.sum(Transaction.amount), 0).label("total"),
                )
                .where(Transaction.date >= start_date, Transaction.date <= end_date)
                .where(Transaction.type.in_(["debit", "credit"]))
                .group_by(Transaction.date, Transaction.type)
            ).all()

            by_day: dict[date, dict[str, Decimal]] = {}
            for r in rows:
                day = r.d
                by_day.setdefault(day, {})
                by_day[day][r.t] = r.total

            data_points: list[dict[str, Any]] = []
            cumulative_expenses = Decimal("0.00")
            cumulative_income = Decimal("0.00")

            cur = start_date
            while cur <= end_date:
                expenses = by_day.get(cur, {}).get("debit", Decimal("0.00"))
                income = by_day.get(cur, {}).get("credit", Decimal("0.00"))

                cumulative_expenses += expenses
                cumulative_income += income

                data_points.append(
                    {
                        "date": cur.isoformat(),
                        "total_expenses": _to_float(expenses),
                        "total_income": _to_float(income),
                    }
                )
                cur += timedelta(days=1)

            return {
                "granularity": "daily",
                "period": _serialize_period(start_date, end_date),
                "data_points": data_points,
                "cumulative_expenses": _to_float(cumulative_expenses),
                "cumulative_income": _to_float(cumulative_income),
            }

        # monthly
        # Range: earliest month (months_back_eff-1 months ago) through end of current month
        start_year, start_month = _add_months(
            year_eff, month_eff, -(months_back_eff - 1)
        )
        start_date = date(start_year, start_month, 1)
        end_start = date(year_eff, month_eff, 1)
        end_day = monthrange(end_start.year, end_start.month)[1]
        end_date = date(end_start.year, end_start.month, end_day)

        rows = session.execute(
            select(
                Transaction.date.label("d"),
                Transaction.type.label("t"),
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            )
            .where(Transaction.date >= start_date, Transaction.date <= end_date)
            .where(Transaction.type.in_(["debit", "credit"]))
            .group_by(Transaction.date, Transaction.type)
        ).all()

        totals_by_month: dict[date, dict[str, Decimal]] = {}
        for r in rows:
            mkey = _first_day_of_month(r.d)
            totals_by_month.setdefault(mkey, {})
            totals_by_month[mkey][r.t] = totals_by_month[mkey].get(
                r.t, Decimal("0.00")
            ) + (r.total or Decimal("0.00"))

        data_points: list[dict[str, Any]] = []
        cumulative_expenses = Decimal("0.00")
        cumulative_income = Decimal("0.00")

        y, m = start_year, start_month
        for _ in range(months_back_eff):
            mkey = date(y, m, 1)
            expenses = totals_by_month.get(mkey, {}).get("debit", Decimal("0.00"))
            income = totals_by_month.get(mkey, {}).get("credit", Decimal("0.00"))

            cumulative_expenses += expenses
            cumulative_income += income

            data_points.append(
                {
                    "date": mkey.isoformat(),
                    "total_expenses": _to_float(expenses),
                    "total_income": _to_float(income),
                }
            )

            y, m = _add_months(y, m, 1)

        return {
            "granularity": "monthly",
            "period": _serialize_period(start_date, end_date),
            "data_points": data_points,
            "cumulative_expenses": _to_float(cumulative_expenses),
            "cumulative_income": _to_float(cumulative_income),
        }
    except Exception:
        raise_api_error(
            500, "AGGREGATION_FAILED", "Failed to compute dashboard aggregation"
        )
    finally:
        session.close()


def _compute_invoice_status(
    closing_date: date,
    due_date: date,
    has_payment: bool,
    today: date | None = None,
) -> str:
    today_eff = today or date.today()
    if has_payment:
        return "paid"
    if today_eff <= closing_date:
        return "open"
    if today_eff <= due_date:
        return "closed"
    return "overdue"


@app.get("/api/v1/dashboard/card-tracking")
def get_card_tracking(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None),
):
    today = date.today()
    month_eff = month if month is not None else today.month
    year_eff = year if year is not None else today.year
    _validate_month_year(month_eff, year_eff)

    session = SessionLocal()
    try:
        cards = (
            session.execute(
                select(Account)
                .where(Account.is_active.is_(True))
                .where(Account.type == "credit_card")
            )
            .scalars()
            .all()
        )

        if not cards:
            return {
                "month": month_eff,
                "year": year_eff,
                "cards": [],
                "upcoming_payments": [],
                "total_card_debt": 0.0,
            }

        card_items: list[dict[str, Any]] = []
        upcoming: list[dict[str, Any]] = []
        total_card_debt = Decimal("0.00")

        for card in cards:
            closing_day = int(card.closing_day or 1)
            due_day = int(card.due_day or 1)

            closing_date = date(
                year_eff,
                month_eff,
                clamp_day_of_month(year_eff, month_eff, closing_day),
            )

            # prev closing to build cycle_start
            prev_year, prev_month = _add_months(year_eff, month_eff, -1)
            prev_closing_date = date(
                prev_year,
                prev_month,
                clamp_day_of_month(prev_year, prev_month, closing_day),
            )
            cycle_start = prev_closing_date + timedelta(days=1)
            cycle_end = closing_date

            invoice_sum = session.execute(
                select(
                    func.coalesce(func.sum(Transaction.amount), 0),
                    func.count(Transaction.id),
                )
                .where(Transaction.account_id == str(card.id))
                .where(Transaction.date >= cycle_start, Transaction.date <= cycle_end)
                .where(Transaction.type == "debit")
            ).one()

            current_invoice_total = invoice_sum[0] or Decimal("0.00")
            transaction_count = int(invoice_sum[1] or 0)

            # due date can fall in next month
            due_year, due_month = year_eff, month_eff
            if due_day < closing_day:
                due_year, due_month = _add_months(year_eff, month_eff, 1)

            due_date = date(
                due_year,
                due_month,
                clamp_day_of_month(due_year, due_month, due_day),
            )

            # payment detection (heuristic): credit tx up to due_date for this cycle
            payment_count = session.execute(
                select(func.count(Transaction.id))
                .where(Transaction.account_id == str(card.id))
                .where(Transaction.date >= cycle_start, Transaction.date <= due_date)
                .where(Transaction.type == "credit")
            ).scalar_one()

            has_payment = int(payment_count or 0) > 0

            status = _compute_invoice_status(
                closing_date=closing_date,
                due_date=due_date,
                has_payment=has_payment,
                today=today,
            )

            days_until_due = (due_date - today).days

            if status != "paid":
                total_card_debt += current_invoice_total

            card_items.append(
                {
                    "account_id": card.id,
                    "account_name": card.name,
                    "current_invoice_total": _to_float(current_invoice_total),
                    "transaction_count": transaction_count,
                    "closing_date": closing_date.isoformat(),
                    "due_date": due_date.isoformat(),
                    "status": status,
                    "days_until_due": days_until_due,
                }
            )

            if status in ("open", "closed"):
                is_urgent = days_until_due <= 5
                upcoming.append(
                    {
                        "account_id": card.id,
                        "account_name": card.name,
                        "due_date": due_date.isoformat(),
                        "amount": _to_float(current_invoice_total),
                        "days_until_due": days_until_due,
                        "is_urgent": bool(is_urgent),
                    }
                )

        upcoming_sorted = sorted(upcoming, key=lambda x: x["due_date"])

        return {
            "month": month_eff,
            "year": year_eff,
            "cards": card_items,
            "upcoming_payments": upcoming_sorted,
            "total_card_debt": _to_float(total_card_debt),
        }
    except Exception:
        raise_api_error(
            500, "AGGREGATION_FAILED", "Failed to compute dashboard aggregation"
        )
    finally:
        session.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}
