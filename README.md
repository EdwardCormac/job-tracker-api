# Job Application Tracker API

[![CI](https://github.com/EdwardCormac/job-tracker-api/actions/workflows/ci.yml/badge.svg)](https://github.com/EdwardCormac/job-tracker-api/actions/workflows/ci.yml)

A REST API for tracking job applications, built with FastAPI, SQLAlchemy and PostgreSQL.
You can create applications, move them through statuses (applied → interview → offer / rejected),
filter by status and page through results.

## Tech stack

- **FastAPI** and **Pydantic v2** for routing, validation and OpenAPI docs
- **SQLAlchemy 2.0** ORM with **PostgreSQL** (SQLite for quick local runs)
- **Alembic** for schema migrations
- **PyTest** with an isolated in-memory test database
- **Docker** and **Docker Compose** for running the API with Postgres
- **GitHub Actions** CI: runs the test suite and builds the Docker image on every pull request

## API

| Method | Path | Description | Success |
|---|---|---|---|
| `POST` | `/applications` | Create an application | `201` |
| `GET` | `/applications` | List applications, newest first. Query: `status`, `limit` (1–100, default 20), `offset` | `200` |
| `GET` | `/applications/{id}` | Get one application | `200` |
| `PATCH` | `/applications/{id}` | Update only the fields you send | `200` |
| `DELETE` | `/applications/{id}` | Delete an application | `204` |

Errors return JSON with a `detail` field: `404` for an unknown id, `422` for invalid input,
`503` when the database is unreachable, and `500` (without internal details) for anything unexpected.

Interactive docs are at `/docs` once the API is running.

## Running with Docker Compose

```bash
docker compose up --build
```

This starts PostgreSQL 17 and the API. The API waits for Postgres to pass its healthcheck,
applies migrations (`alembic upgrade head`), then serves on http://localhost:8000.
Data is stored in a named volume, so it survives restarts; `docker compose down -v` deletes it.

## Running locally

Requires Python 3.13.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env            # defaults to a local SQLite database
alembic upgrade head
uvicorn app.main:app --reload
```

## Running the tests

```bash
pytest
```

Tests run against an in-memory SQLite database that is created and dropped for each test,
so they never touch your local data.

## Project structure

```
app/
  config.py       settings loaded from environment variables / .env
  database.py     engine, session factory, get_db dependency
  models.py       SQLAlchemy model and status enum
  schemas.py      Pydantic request and response models
  crud.py         database operations
  main.py         FastAPI app, routes and error handlers
alembic/          migration environment and versions
tests/            PyTest suite and fixtures
```

## Design notes

- **Migrations own the schema.** The app never calls `create_all`; tables are created only by Alembic.
- **PATCH is a true partial update.** Only fields present in the request are changed;
  sending `null` clears optional fields but is rejected for required ones.
- **Status is enforced twice:** by Pydantic at the API boundary and by a database `CHECK` constraint.
- **The container runs as a non-root user** and starts uvicorn with `exec`, so `docker stop` shuts it down gracefully.

## Roadmap

Planned, not yet built:

- `/health` readiness endpoint
- Structured logging
- Prometheus metrics and a Grafana dashboard
- Running the test suite against PostgreSQL in CI
- Optional: JWT authentication and status-change history
