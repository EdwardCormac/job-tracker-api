from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app


class UnreachableSession:
    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def unreachable_db() -> UnreachableSession:
    return UnreachableSession()


def test_liveness_returns_ok(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_ignores_database_outage(client: TestClient) -> None:
    def broken_db() -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_db] = broken_db

    response = client.get("/health/live")

    assert response.status_code == 200


def test_readiness_returns_ok_when_database_reachable(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_favicon_returns_no_content(client: TestClient) -> None:
    response = client.get("/favicon.ico")

    assert response.status_code == 204
    assert response.content == b""


def test_readiness_returns_503_when_database_unreachable(client: TestClient) -> None:
    app.dependency_overrides[get_db] = unreachable_db

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}
