from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
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
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    desc,
    func,
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

    id = Column(String(36), primary_key=True)
    import_file_id = Column(String(36), nullable=True, index=True)
    account_id = Column(String(36), nullable=True)
    date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    type = Column(String(10), nullable=False)
    category_id = Column(String(36), nullable=True)
    hash = Column(String(64), nullable=False, unique=True, index=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


Base.metadata.create_all(bind=engine)

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
        id=str(uuid4()),
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


@app.get("/health")
def health_check():
    return {"status": "ok"}
