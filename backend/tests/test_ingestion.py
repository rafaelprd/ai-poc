from __future__ import annotations

import importlib
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    db_path = tmp_path / "financeiro_test.db"
    upload_dir = tmp_path / "uploads"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))

    sys.modules.pop("backend.app", None)
    module = importlib.import_module("backend.app")
    module = importlib.reload(module)

    yield module

    sys.modules.pop("backend.app", None)


@pytest.fixture()
def client(app_module):
    return TestClient(app_module.app)


def test_parse_helpers_normalize_values(app_module):
    assert app_module.parse_date("10/07/2025") == date(2025, 7, 10)
    assert app_module.parse_date("2025-07-10") == date(2025, 7, 10)

    assert app_module.parse_amount("R$ 1.234,56") == Decimal("1234.56")
    assert app_module.parse_amount("-12,50") == Decimal("-12.50")
    assert app_module.parse_amount("(12.50)") == Decimal("-12.50")

    h1 = app_module.compute_hash(
        date(2025, 7, 10),
        " Compra   Mercado ",
        Decimal("12.50"),
    )
    h2 = app_module.compute_hash(
        date(2025, 7, 10),
        "compra mercado",
        Decimal("12.50"),
    )
    assert h1 == h2


def test_upload_csv_creates_batch_and_skips_duplicates(client):
    csv_data = (
        "data;descricao;valor\n"
        "10/07/2025;Compra Mercado;-12,50\n"
        "11/07/2025;Salario;1000,00\n"
        "10/07/2025;Compra Mercado;-12,50\n"
    )

    response = client.post(
        "/api/v1/ingestion/upload",
        data={"account_id": "123e4567-e89b-12d3-a456-426614174000"},
        files={"files": ("statement.csv", csv_data, "text/csv")},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    assert len(body["files"]) == 1

    batch_id = body["batch_id"]

    status_response = client.get(f"/api/v1/ingestion/batches/{batch_id}")
    assert status_response.status_code == 200

    status_body = status_response.json()
    assert status_body["batch_id"] == batch_id
    assert status_body["status"] == "completed"
    assert status_body["total_transactions_created"] == 2
    assert status_body["duplicates_skipped"] == 1

    assert len(status_body["files"]) == 1
    assert status_body["files"][0]["status"] == "completed"
    assert status_body["files"][0]["rows_extracted"] == 3
    assert status_body["files"][0]["rows_failed"] == 0


def test_upload_csv_with_bad_row_logs_error_and_marks_partial_failure(client):
    csv_data = (
        "data;descricao;valor\n15/13/2025;Bad Date;10,00\n10/07/2025;Good Row;5,00\n"
    )

    response = client.post(
        "/api/v1/ingestion/upload",
        files={"files": ("bad_rows.csv", csv_data, "text/csv")},
    )

    assert response.status_code == 202
    batch_id = response.json()["batch_id"]

    status_response = client.get(f"/api/v1/ingestion/batches/{batch_id}")
    assert status_response.status_code == 200

    status_body = status_response.json()
    assert status_body["status"] == "partial_failure"
    assert status_body["total_transactions_created"] == 1
    assert status_body["duplicates_skipped"] == 0
    assert status_body["files"][0]["status"] == "completed"
    assert status_body["files"][0]["rows_extracted"] == 1
    assert status_body["files"][0]["rows_failed"] == 1

    errors_response = client.get(f"/api/v1/ingestion/batches/{batch_id}/errors")
    assert errors_response.status_code == 200

    errors_body = errors_response.json()
    assert errors_body["batch_id"] == batch_id
    assert errors_body["total"] == 1
    assert len(errors_body["errors"]) == 1
    assert errors_body["errors"][0]["error_type"] == "INVALID_DATE"
    assert "month 13 out of range" in errors_body["errors"][0]["error_message"]


def test_upload_rejects_invalid_file_format(client):
    response = client.post(
        "/api/v1/ingestion/upload",
        files={"files": ("note.txt", b"just text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_FILE_FORMAT"


def test_upload_rejects_too_many_files(client):
    files = [
        (
            "files",
            (
                f"file_{index}.csv",
                "data;descricao;valor\n10/07/2025;Row;1,00\n",
                "text/csv",
            ),
        )
        for index in range(21)
    ]

    response = client.post(
        "/api/v1/ingestion/upload",
        files=files,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "TOO_MANY_FILES"


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/api/v1/ingestion/upload",
        files={"files": ("empty.csv", b"", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "EMPTY_FILE"


def test_batch_errors_paginate(client):
    csv_data = (
        "data;descricao;valor\n"
        "15/13/2025;Bad One;10,00\n"
        "16/13/2025;Bad Two;20,00\n"
        "10/07/2025;Good Row;5,00\n"
    )

    response = client.post(
        "/api/v1/ingestion/upload",
        files={"files": ("errors.csv", csv_data, "text/csv")},
    )

    assert response.status_code == 202
    batch_id = response.json()["batch_id"]

    errors_response = client.get(
        f"/api/v1/ingestion/batches/{batch_id}/errors?page=1&page_size=1"
    )
    assert errors_response.status_code == 200

    errors_body = errors_response.json()
    assert errors_body["batch_id"] == batch_id
    assert errors_body["total"] == 2
    assert errors_body["page"] == 1
    assert errors_body["page_size"] == 1
    assert len(errors_body["errors"]) == 1

    second_page = client.get(
        f"/api/v1/ingestion/batches/{batch_id}/errors?page=2&page_size=1"
    )
    assert second_page.status_code == 200
    assert second_page.json()["total"] == 2
    assert len(second_page.json()["errors"]) == 1


def test_list_batches_returns_created_batch(client):
    csv_data = "data;descricao;valor\n10/07/2025;One;1,00\n"

    response = client.post(
        "/api/v1/ingestion/upload",
        files={"files": ("one.csv", csv_data, "text/csv")},
    )

    assert response.status_code == 202

    list_response = client.get("/api/v1/ingestion/batches")
    assert list_response.status_code == 200

    body = list_response.json()
    assert body["total"] >= 1
    assert len(body["batches"]) >= 1
    assert body["batches"][0]["status"] in {
        "processing",
        "completed",
        "partial_failure",
        "failed",
    }


def test_reupload_same_csv_creates_no_new_transactions(client):
    csv_data = (
        "data;descricao;valor\n"
        "10/07/2025;Compra Mercado;-12,50\n"
        "11/07/2025;Salario;1000,00\n"
    )

    first_response = client.post(
        "/api/v1/ingestion/upload",
        files={"files": ("statement.csv", csv_data, "text/csv")},
    )
    assert first_response.status_code == 202

    first_batch_id = first_response.json()["batch_id"]
    first_status = client.get(f"/api/v1/ingestion/batches/{first_batch_id}")
    assert first_status.status_code == 200
    assert first_status.json()["total_transactions_created"] == 2

    second_response = client.post(
        "/api/v1/ingestion/upload",
        files={"files": ("statement.csv", csv_data, "text/csv")},
    )
    assert second_response.status_code == 202

    second_batch_id = second_response.json()["batch_id"]
    second_status = client.get(f"/api/v1/ingestion/batches/{second_batch_id}")
    assert second_status.status_code == 200

    second_body = second_status.json()
    assert second_body["total_transactions_created"] == 0
    assert second_body["duplicates_skipped"] == 2
    assert second_body["status"] in {"completed", "partial_failure"}
