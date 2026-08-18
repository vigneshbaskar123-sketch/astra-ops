"""
Seeds a fresh database with enough realistic demo data to make
`docker compose up` immediately show something meaningful on the
dashboard, rather than an empty shell.

Run with: `python -m app.db.seed_demo_data` (from backend/)

Site coordinates are Vainu Bappu Observatory, Kavalur, Tamil Nadu — a
real IIA-operated site (12.5748N, 78.8205E, 725m) — used here as public,
freely available location data for a plausible demo, not as any claim
about IIA's actual systems. Target RA/Dec are real J2000 catalog
coordinates for well-known objects. Everything else (users, telescope/
instrument specs) is clearly synthetic demo data.
"""
from __future__ import annotations

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.observatory import Instrument, InstrumentType, MountType, Observatory, Telescope
from app.models.target import Target, TargetType
from app.models.user import User, UserRole

import app.models  # noqa: F401


DEMO_TARGETS = [
    ("M31 - Andromeda Galaxy", 10.6847, 41.269, TargetType.GALAXY, 3.4),
    ("M42 - Orion Nebula", 83.8221, -5.3911, TargetType.NEBULA, 4.0),
    ("M45 - Pleiades", 56.75, 24.1167, TargetType.STAR_CLUSTER, 1.6),
    ("M13 - Hercules Cluster", 250.4234, 36.4613, TargetType.STAR_CLUSTER, 5.8),
    ("Saturn", 300.0, -20.0, TargetType.PLANET, 0.5),  # RA/Dec vary with date; illustrative demo value
    ("Vega", 279.2347, 38.7837, TargetType.STAR, 0.03),
    ("M51 - Whirlpool Galaxy", 202.4696, 47.1952, TargetType.GALAXY, 8.4),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Observatory).first():
            print("Database already has data — skipping seed. Delete the DB file to reseed.")
            return

        observatory = Observatory(
            name="Vainu Bappu Observatory (demo)",
            code="VBO",
            latitude_deg=12.5748,
            longitude_deg=78.8205,
            elevation_m=725.0,
            timezone="Asia/Kolkata",
            description="Seeded with VBO's real public coordinates for a realistic demo site. "
            "Not connected to any real IIA system.",
        )
        db.add(observatory)
        db.flush()

        telescope = Telescope(
            observatory_id=observatory.id,
            name="ASTRA-SIM-1 (0.5m simulated)",
            aperture_mm=500.0,
            focal_length_mm=4000.0,
            mount_type=MountType.EQUATORIAL,
            is_simulated=True,
        )
        db.add(telescope)
        db.flush()

        instrument = Instrument(
            telescope_id=telescope.id,
            name="SimCam-1",
            instrument_type=InstrumentType.CAMERA,
            pixel_size_um=9.0,
            resolution_x=2048,
            resolution_y=2048,
            bit_depth=16,
            available_filters="L,R,G,B,Ha,OIII,SII",
        )
        db.add(instrument)

        admin = User(
            username="admin",
            email="admin@astra-ops.local",
            full_name="Demo Administrator",
            hashed_password=hash_password("ChangeMe123!"),
            role=UserRole.ADMIN,
        )
        operator = User(
            username="operator",
            email="operator@astra-ops.local",
            full_name="Demo Operator",
            hashed_password=hash_password("ChangeMe123!"),
            role=UserRole.OPERATOR,
        )
        viewer = User(
            username="viewer",
            email="viewer@astra-ops.local",
            full_name="Demo Viewer",
            hashed_password=hash_password("ChangeMe123!"),
            role=UserRole.VIEWER,
        )
        db.add_all([admin, operator, viewer])
        db.flush()

        for name, ra, dec, ttype, mag in DEMO_TARGETS:
            db.add(Target(name=name, ra_deg=ra, dec_deg=dec, target_type=ttype, magnitude=mag, created_by_id=admin.id))

        db.commit()
        print("Seed complete:")
        print(f"  Observatory: {observatory.name}")
        print(f"  Telescope:   {telescope.name}")
        print(f"  Users:       admin / operator / viewer  (password: ChangeMe123! — change before any real deployment)")
        print(f"  Targets:     {len(DEMO_TARGETS)} seeded")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
