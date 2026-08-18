# ASTRA-OPS 🔭

An astronomy observatory operations platform — a modular **FastAPI backend** that plans observations with **real orbital mechanics**, simulates telescope hardware, ingests and analyzes FITS images, and raises rule-based alerts.

Built to manage an observatory end-to-end: from "is this target visible tonight?" to "how good was the last image?"

> **Status:** backend core complete — **57/57 tests passing**, 34 REST endpoints. Frontend, AI assistant, PDF reports, and Docker are the next stages (see [STATUS.md](STATUS.md)).

---

## Features

| # | Module | What it does |
|---|---|---|
| 1 | 🔐 **Authentication** | JWT + bcrypt, RBAC (`admin` / `operator` / `viewer`), logout via token denylist |
| 2 | 🗓️ **Observation Planner** | Real Alt/Az, visibility windows, moon illumination, sun altitude via `astropy`/`astroplan` |
| 3 | 🎯 **Target Management** | CRUD + search for celestial targets (galaxies, nebulae, clusters, planets, stars) |
| 4 | 🌤️ **Weather Monitor** | Diurnal simulation with `SAFE`/`WARNING`/`UNSAFE` classification (worst-factor-wins) |
| 5 | 🔭 **Telescope Simulator** | Realistic slew timing, tracking, dome/camera state — reports **real** Alt/Az from the astronomy engine |
| 6 | 📡 **FITS Data Manager** | 3-layer upload validation, real header extraction, missing-keyword detection |
| 7 | ✨ **Image Quality Analyzer** | `DAOStarFinder` star detection, Gaussian PSF fit for FWHM, transparent weighted scoring |
| 8 | 🚨 **Alert System** | Rule-based alerts on weather / image-quality / missing-metadata / observation failures |
| 9 | 📊 **Analytics** | Aggregation endpoints (observations/day, status breakdown, top targets) |
| 10 | 📑 **Reports** | CSV export (daily / session / image-quality) |
| 11 | 📝 **Observation Logging** | Planner entry → `planned` → `completed`/`failed` lifecycle |
| 12 | 🕵️ **Audit Logging** | Action trail for every auth/security event |

---

## Tech Stack

- **Backend:** FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic
- **Astronomy:** astropy · astroplan · photutils
- **Auth:** python-jose (JWT) · bcrypt · passlib
- **Database:** PostgreSQL (production) / SQLite (dev & test) — schema is fully portable
- **Tests:** pytest — 57 tests

---

## Quick Start

```bash
cd backend

# 1. Create a virtual environment and install dependencies
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt

# 2. (Optional) Copy the env template — defaults work for local SQLite
cp ../.env.example .env

# 3. Seed demo data (real VBO coordinates, 7 catalog targets, 3 demo users)
python -m app.db.seed_demo_data

# 4. Run the server
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for interactive Swagger UI.

### Demo logins

| Username | Role | Password |
|---|---|---|
| `admin` | admin | `ChangeMe123!` |
| `operator` | operator | `ChangeMe123!` |
| `viewer` | viewer | `ChangeMe123!` |

> ⚠️ Change these before any real deployment.

---

## Running the tests

```bash
cd backend
python -m pytest tests/ -v
```

---

## Architecture

```mermaid
flowchart LR
    subgraph Client
        UI[React Frontend<br/>(next stage)]
    end

    subgraph API[FastAPI Backend]
        Auth[Auth · JWT + RBAC]
        Planner[Planner · real astronomy]
        Telescope[Telescope · simulated hw]
        Weather[Weather · simulated]
        Fits[FITS · header extraction]
        ImgQ[Image Quality · star detection]
        Alerts[Alerts · rule-based]
        Analytics[Analytics]
        Reports[Reports · CSV]
    end

    subgraph Services[Domain Services]
        Astro[astronomy.py<br/>astropy + astroplan]
        TelSim[telescope_simulator.py]
        FitsSvc[fits_service.py]
        ImgQSvc[image_quality.py<br/>photutils]
    end

    DB[(PostgreSQL / SQLite)]

    UI --> API
    Planner --> Astro
    Telescope --> TelSim --> Astro
    Fits --> FitsSvc
    ImgQ --> ImgQSvc
    API --> DB
```

### The "real vs. simulated" line

The project's core rule: **never fake what can be computed for real.**

| Data | Real or simulated? |
|---|---|
| Target Alt/Az, sun/moon position, visibility windows | ✅ **Real** — astropy/astroplan orbital mechanics |
| Telescope Alt/Az while slewing/tracking | ✅ **Real** — computed from RA/Dec via the same engine |
| Telescope slew/tracking/dome/camera state | 🔧 Simulated — no physical mount (swap point: `telescope_interface.py`) |
| Weather readings | 🔧 Simulated — no sensor (swap point: `weather_simulator.py`) |
| FITS header metadata | ✅ **Real** — read from the uploaded file |
| Star count / FWHM / SNR / background | ✅ **Real** — measured from actual pixels |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design rationale.

---

## Project Structure

```
astra-ops/
├── backend/
│   ├── app/
│   │   ├── api/          # routes (auth, targets, planner, telescope, ...)
│   │   ├── core/         # config, security (JWT, bcrypt, RBAC)
│   │   ├── db/           # SQLAlchemy session + demo data seed
│   │   ├── models/       # 12 SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # astronomy, telescope sim, weather, FITS, image quality, alerts, audit
│   ├── alembic/          # database migrations
│   ├── tests/            # 57 tests + synthetic image fixtures
│   └── requirements.txt
├── frontend/             # (next stage — React/Vite/TS)
├── docker/               # (next stage)
├── ARCHITECTURE.md
├── STATUS.md
└── README.md
```

---

## Roadmap (next stages)

- [ ] **Frontend** — React/Vite/TypeScript/Tailwind/Chart.js (12 pages)
- [ ] **Frontend ↔ backend integration**
- [ ] **AI Observation Assistant** — Claude API, grounded in real computed values (`ANTHROPIC_API_KEY` already reserved in config)
- [ ] **PDF reports** — CSV works now; PDF needs a design pass
- [ ] **Docker + docker-compose**

---

## License

No license is attached yet. If you intend to reuse this code, please add a `LICENSE` file (e.g. MIT or Apache-2.0).
