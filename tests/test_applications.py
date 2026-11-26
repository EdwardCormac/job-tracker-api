from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app


def make_application(client: TestClient, **overrides: object) -> dict:
    payload = {"company": "BMW TechWorks", "role": "Python Developer"} | overrides
    response = client.post("/applications", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_application_applies_defaults_and_normalises(client: TestClient) -> None:
    response = client.post(
        "/applications",
        json={"company": "  BMW TechWorks ", "role": "Python Developer", "job_url": "https://Example.com"},
    )

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["company"] == "BMW TechWorks"
    assert body["status"] == "applied"
    assert body["job_url"] == "https://example.com/"
    assert body["applied_date"] == date.today().isoformat()
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


@pytest.mark.parametrize(
    ("payload", "bad_field"),
    [
        ({"role": "Dev"}, "company"),
        ({"company": "   ", "role": "Dev"}, "company"),
        ({"company": "X" * 201, "role": "Dev"}, "company"),
        ({"company": "BMW", "role": "Dev", "status": "Interview"}, "status"),
        ({"company": "BMW", "role": "Dev", "job_url": "bmw.com"}, "job_url"),
        ({"company": "BMW", "role": "Dev", "applied_date": "26/11/2026"}, "applied_date"),
    ],
)
def test_create_application_rejects_invalid_input(client: TestClient, payload: dict, bad_field: str) -> None:
    response = client.post("/applications", json=payload)

    assert response.status_code == 422
    assert ["body", bad_field] in [error["loc"] for error in response.json()["detail"]]


def test_get_application_returns_it(client: TestClient) -> None:
    created = make_application(client)

    response = client.get(f"/applications/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_application_returns_404(client: TestClient) -> None:
    response = client.get("/applications/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Application 999 not found"}


def test_list_filters_by_status(client: TestClient) -> None:
    make_application(client, company="A", status="interview")
    make_application(client, company="B", status="applied")
    make_application(client, company="C", status="interview")

    response = client.get("/applications", params={"status": "interview"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["company"] for item in body["items"]} == {"A", "C"}


def test_list_paginates_newest_first(client: TestClient) -> None:
    for day in range(1, 6):
        make_application(client, company=f"Company {day}", applied_date=f"2026-11-0{day}")

    response = client.get("/applications", params={"limit": 2, "offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert [item["company"] for item in body["items"]] == ["Company 3", "Company 2"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"status": "ghosted"}])
def test_list_rejects_invalid_query_params(client: TestClient, params: dict) -> None:
    response = client.get("/applications", params=params)

    assert response.status_code == 422


def test_update_changes_only_sent_fields(client: TestClient) -> None:
    created = make_application(client, notes="Referred by a friend")

    response = client.patch(f"/applications/{created['id']}", json={"status": "interview"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "interview"
    assert body["notes"] == "Referred by a friend"
    assert body["company"] == created["company"]


def test_update_can_clear_optional_field(client: TestClient) -> None:
    created = make_application(client, notes="Old note")

    response = client.patch(f"/applications/{created['id']}", json={"notes": None})

    assert response.status_code == 200
    assert response.json()["notes"] is None


def test_update_rejects_null_for_required_field(client: TestClient) -> None:
    created = make_application(client)

    response = client.patch(f"/applications/{created['id']}", json={"company": None})

    assert response.status_code == 422
    assert "company cannot be null" in response.text


def test_update_unknown_application_returns_404(client: TestClient) -> None:
    response = client.patch("/applications/999", json={"status": "offer"})

    assert response.status_code == 404


def test_delete_removes_application(client: TestClient) -> None:
    created = make_application(client)

    response = client.delete(f"/applications/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/applications/{created['id']}").status_code == 404


def test_delete_unknown_application_returns_404(client: TestClient) -> None:
    response = client.delete("/applications/999")

    assert response.status_code == 404


def test_database_unavailable_returns_503(client: TestClient) -> None:
    def broken_db() -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_db] = broken_db

    response = client.get("/applications")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable, please try again later"}


def test_unexpected_error_returns_generic_json_500(client: TestClient) -> None:
    def buggy_db() -> None:
        raise RuntimeError("secret internal detail")

    app.dependency_overrides[get_db] = buggy_db
    non_raising_client = TestClient(app, raise_server_exceptions=False)

    response = non_raising_client.get("/applications")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret internal detail" not in response.text
