# ASTRA-OPS — Build Status

This is a staged build (see the original brief's own "first do X, then Y"
instruction). This file tracks exactly what's done vs. pending so nothing
gets silently skipped.

## Done and tested (57/57 automated tests passing)

- Full backend folder structure and modular architecture
- Database schema: all 12 tables, SQLAlchemy 2.0, Postgres + SQLite portable
- Alembic migrations (initial schema generated, upgrade/downgrade both verified)
- Auth: JWT, bcrypt hashing, RBAC (admin/operator/viewer), logout via token denylist
- Astronomy engine: Alt/Az, sun/moon, illumination, visibility windows — astropy/astroplan
- Telescope simulator: realistic slew timing, tracking, dome/camera state, real Alt/Az
- Weather simulator: diurnal model, documented SAFE/WARNING/UNSAFE thresholds
- Target CRUD + search
- Observation planner (real visibility calculations) and observation logging (planned -> completed/failed)
- FITS upload: 3-layer validation, real astropy header extraction, missing-keyword detection
- Image quality analyzer: DAOStarFinder, Gaussian PSF fit for FWHM, sigma-clipped background, transparent weighted scoring
- Alerts: rule-based, triggered by weather/image-quality/missing-metadata/observation-failure events
- Analytics aggregation endpoints
- Audit logging service
- Reports: CSV export (daily / session / image-quality)
- Demo data seed script (real VBO coordinates, 7 real-catalog targets, 3 demo users)
- 34 REST endpoints, all exercised end-to-end against seeded data, not just unit-tested in isolation

## Not started yet (next stages, in the brief's original order)

- Frontend (React/Vite/TS/Tailwind/Chart.js) — all 12 pages
- Frontend/backend integration
- AI Observation Assistant (planned: Claude API, answers grounded only in
  real computed values from the modules above — see `AI_ASSISTANT_MODEL`
  / `ANTHROPIC_API_KEY` already reserved in config)
- PDF reports (CSV works now; PDF needs a design pass + Claude's `pdf` skill)
- Docker + docker-compose
- Full top-level README (this file + ARCHITECTURE.md are the interim docs)

## Run it right now (no Docker yet)

```bash
cd backend
pip install -r requirements.txt --break-system-packages   # or use a venv
cp ../.env.example .env      # defaults work as-is for local SQLite

python -m app.db.seed_demo_data     # creates astra_ops.db with demo data
uvicorn app.main:app --reload       # http://localhost:8000/docs for interactive API docs
```

Demo logins (seeded, change before any real deployment):
`admin` / `operator` / `viewer`, all with password `ChangeMe123!`.

Run the test suite:

```bash
cd backend
python -m pytest tests/ -v
```

Run Alembic migrations against Postgres instead of the SQLite default:

```bash
DATABASE_URL="postgresql+psycopg2://user:pass@localhost/astra_ops" python -m alembic upgrade head
```
