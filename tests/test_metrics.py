from fastapi.testclient import TestClient
from prometheus_client import REGISTRY


def sample(name: str, labels: dict[str, str]) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    client.get("/applications")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds_bucket" in response.text


def test_requests_are_counted_by_route_template(client: TestClient) -> None:
    labels = {"method": "GET", "route": "/applications/{application_id}", "status_code": "404"}
    before = sample("http_requests_total", labels)

    client.get("/applications/998")
    client.get("/applications/999")

    assert sample("http_requests_total", labels) == before + 2
    raw_path_labels = {"method": "GET", "route": "/applications/999", "status_code": "404"}
    assert REGISTRY.get_sample_value("http_requests_total", raw_path_labels) is None


def test_unmatched_paths_share_one_label(client: TestClient) -> None:
    labels = {"method": "GET", "route": "unmatched", "status_code": "404"}
    before = sample("http_requests_total", labels)

    client.get("/does-not-exist")
    client.get("/wp-admin")

    assert sample("http_requests_total", labels) == before + 2


def test_request_duration_is_observed(client: TestClient) -> None:
    labels = {"method": "GET", "route": "/applications"}
    before = sample("http_request_duration_seconds_count", labels)

    client.get("/applications")

    assert sample("http_request_duration_seconds_count", labels) == before + 1
