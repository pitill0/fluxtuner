# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from fluxtuner.core import db

router = APIRouter()


@router.get("/api/public/stats")
def public_stats() -> dict[str, Any]:
    with db.connect() as conn:
        return db.public_activity_stats(conn)
