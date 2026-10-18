# Local setup

## Requirements

Python 3.12+, Node 24+, npm and Docker Desktop (for PostgreSQL). No cloud account or credential is required for local development.

## API

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env
.venv\Scripts\alembic upgrade head
.venv\Scripts\uvicorn expense_intelligence.main:app --app-dir apps/api --reload
```

The commands above use SQLite. They do not modify the PostgreSQL setup or vice versa.

## PostgreSQL 16 with Docker

Create the ignored local credentials file once, choose a development-only password, then start only this project's database service:

```powershell
Copy-Item .env.postgres.example .env.postgres
# Edit .env.postgres and replace the placeholder password.
docker compose up -d postgres
docker compose ps
```

The named `expenseintelligence_expense_pg_data` volume persists local data. PostgreSQL is published only on `127.0.0.1`; it is not reachable through other host interfaces. Compose does not containerize the API or web app.

Set the matching password only in your current shell before running the API or migrations. Do not commit the resulting URL:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://expense:<local-password>@127.0.0.1:5432/expense_intelligence"
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn expense_intelligence.main:app --app-dir apps/api --reload
```

Run Next.js in another terminal with `npm.cmd run dev:web`. To stop PostgreSQL without deleting its named volume, run `docker compose stop postgres`.

### PostgreSQL tests

Use a disposable database, never the development database, because the test fixture recreates its schema between tests:

```powershell
docker compose exec -T postgres createdb -U expense expense_app_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://expense:<local-password>@127.0.0.1:5432/expense_app_test"
.venv\Scripts\python -m pytest
Remove-Item Env:TEST_DATABASE_URL
```

To test the complete reversible migration chain, create a separate disposable database:

```powershell
docker compose exec -T postgres createdb -U expense expense_migration_test
$env:DATABASE_URL = "postgresql+psycopg://expense:<local-password>@127.0.0.1:5432/expense_migration_test"
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic downgrade base
.venv\Scripts\python -m alembic upgrade head
Remove-Item Env:DATABASE_URL
```

## Web

```powershell
npm.cmd install
npm.cmd run dev:web
```

Open `http://localhost:3000`. `NEXT_PUBLIC_DEV_USER_ID` becomes an `X-Dev-User-Id` header only for the explicitly local configuration. Hosted configuration rejects this mechanism and requires a valid Supabase bearer token.

## Tests and checks

```powershell
.venv\Scripts\python -m pytest
npm.cmd run test:web
npm.cmd --workspace apps/web run eval:ocr
npm.cmd run lint:web
npm.cmd run build:web
```

## Not configured

Google OAuth/Supabase JWKS values, hosted PostgreSQL, cloud deployment and background jobs are intentionally absent. Gemini remains disabled by default and document processing remains browser-local. Never put credentials in `Creds.txt`, committed files, or `NEXT_PUBLIC_*` variables.
