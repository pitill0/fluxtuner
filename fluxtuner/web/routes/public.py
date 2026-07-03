# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from fluxtuner.core import db
from fluxtuner.web import context as web_context

router = APIRouter()


@router.get("/api/public/stats")
def public_stats() -> dict[str, Any]:
    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return db.public_activity_stats(conn)
