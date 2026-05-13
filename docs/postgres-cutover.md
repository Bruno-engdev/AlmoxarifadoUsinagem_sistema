# PostgreSQL Cutover Checklist

End-to-end procedure to migrate AlmoxarifadoUsinagem from SQLite to PostgreSQL.
SQLite remains a supported fallback for local development.

## 0. Pre-flight

- [ ] Backup current SQLite: `Copy-Item toolcrib.db toolcrib.backup-cutover.db`
- [ ] Confirm `requirements.txt` has `alembic` and `psycopg[binary]`.
- [ ] Confirm `.env` (copy from `.env.example`) has the desired credentials.
- [ ] Stop any running `web` container that still uses SQLite.

## 1. Bring up Postgres only

```powershell
docker compose up -d db
docker compose ps        # db should be "healthy"
```

## 2. Apply schema via Alembic

Run from a one-shot container so the app image's environment is used:

```powershell
docker compose run --rm `
  -e DATABASE_URL=postgresql+psycopg://toolcrib:toolcrib@db:5432/toolcrib `
  --no-deps web alembic upgrade head
```

Verify:
```powershell
docker compose exec db psql -U toolcrib -d toolcrib -c "\dt"
```

Expected tables: `alembic_version`, `users`, `machines`, `tool_types`,
`employees`, `tools`, `tool_parameters`, `movements`, `tool_stock_alerts`.

## 3. Migrate data from SQLite

The host's `toolcrib.db` is NOT inside the image anymore. Mount it into a
one-shot run:

```powershell
docker compose run --rm `
  -v ${PWD}/toolcrib.db:/data/toolcrib.db:ro `
  -e DATABASE_URL=postgresql+psycopg://toolcrib:toolcrib@db:5432/toolcrib `
  --no-deps web `
  python -m app.migrate_sqlite_to_postgres `
    --source sqlite:////data/toolcrib.db `
    --target postgresql+psycopg://toolcrib:toolcrib@db:5432/toolcrib
```

Inspect the verification block: every table's `src` count must equal `dst`.

If the network/UNC mount blocks the bind (Docker Desktop on this workspace has
failed before for single-file mounts), copy `toolcrib.db` to a local path first
(e.g. `C:\temp\toolcrib.db`) and mount from there.

## 4. Start the web service

```powershell
docker compose up -d web
docker compose logs -f web
```

`entrypoint.sh` will run `alembic upgrade head` (no-op, already at head) and
`python -m app.cli seed` (idempotent), then start uvicorn.

## 5. Functional smoke test (PostgreSQL)

Login + critical flows. Tick each:

- [ ] `/login` accepts the existing admin (or newly seeded `admin/admin`).
- [ ] `/` dashboard renders without 500.
- [ ] `/tools` lists tools with the correct count.
- [ ] Tool detail page opens; parameters render.
- [ ] Create OUT movement (emprestimo) -> stock decreases, movement appears in history.
- [ ] Create IN movement (reposicao) -> stock increases, alert clears if applicable.
- [ ] `/employees`, `/machines`, `/tool-types` CRUD round-trip.
- [ ] `/notifications` shows existing `tool_stock_alerts`.
- [ ] Excel export endpoints download a non-empty `.xlsx`.
- [ ] `/admin/users` accessible to ADMIN; create/edit/disable user.

## 6. Sequence sanity (Postgres-only)

After the migration script, every sequence is set to MAX(id). Insert a brand
new row in any table (e.g. create a tool) and confirm the new id is
MAX(previous_id)+1.

```powershell
docker compose exec db psql -U toolcrib -d toolcrib -c "SELECT MAX(id) FROM movements;"
```

Then create a movement via the UI and re-run the query: it must increment by 1.

## 7. Rollback plan (until cutover is final)

The original `toolcrib.db` is untouched — the migration is a copy, not a move.
To revert to SQLite locally:

```powershell
$env:DATABASE_URL = $null              # falls back to repo-root SQLite
uvicorn app.main:app
```

Or, in Docker, override the compose file with a profile that points `web` at
SQLite again. Keep `toolcrib.backup-cutover.db` until step 5 is fully green.

## 8. Promote PostgreSQL as primary

Once steps 1–6 are green:

- [ ] Document the new `DATABASE_URL` in the project README.
- [ ] Communicate the change to the team and link this checklist.
- [ ] Schedule periodic `pg_dump` of the `pgdata` volume.
- [ ] Optionally remove `toolcrib.db` from the repository root after a grace
      period (keep it in backups).

## Known pitfalls

- Do NOT `alembic upgrade head` against an existing populated SQLite without
  stamping first; use `alembic stamp 0001_baseline`.
- Do NOT run the migration script with a non-empty target — it will fail by
  design. Use `--allow-non-empty-target` only if you understand the FK and
  sequence implications.
- Bind-mounting a single SQLite file from a UNC path under Docker Desktop on
  this workstation has failed before. Copy the file to a local disk path first.
- The web image no longer ships `toolcrib.db`. Any `docker compose up` without
  a healthy `db` service will fail by design.
