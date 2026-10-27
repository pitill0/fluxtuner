# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from time import monotonic

from fluxtuner.core import db, recovery_codes
from fluxtuner.web import auth, reauth_attempts

AUTH_ATTEMPT_RETENTION_SECONDS = 24 * 60 * 60
AUTH_MAINTENANCE_INTERVAL_SECONDS = 60 * 60

_auth_maintenance_lock = Lock()
_last_auth_maintenance_monotonic: float | None = None


@dataclass(frozen=True)
class AuthMaintenanceResult:
    expired_sessions: int
    old_login_attempts: int
    old_recovery_attempts: int
    old_reauth_attempts: int = 0
    expired_refresh_receipts: int = 0


def run_auth_maintenance(
    *,
    now: datetime | None = None,
) -> AuthMaintenanceResult:
    with db.connect() as conn:
        expired_sessions = auth.purge_expired_sessions(
            conn,
            now=now,
        )
        old_login_attempts = auth.purge_old_login_attempts(
            conn,
            now=now,
            window_seconds=AUTH_ATTEMPT_RETENTION_SECONDS,
        )
        old_recovery_attempts = recovery_codes.purge_old_recovery_attempts(
            conn,
            now=now,
            window_seconds=AUTH_ATTEMPT_RETENTION_SECONDS,
        )
        old_reauth_attempts = reauth_attempts.purge_old_reauth_attempts(
            conn,
            now=now,
            window_seconds=AUTH_ATTEMPT_RETENTION_SECONDS,
        )
        expired_refresh_receipts = conn.execute(
            "DELETE FROM remote_catalog_refresh_receipts WHERE expires_at < ?",
            ((now or datetime.now(UTC)).isoformat(),),
        ).rowcount
        conn.commit()

    return AuthMaintenanceResult(
        expired_sessions=expired_sessions,
        old_login_attempts=old_login_attempts,
        old_recovery_attempts=old_recovery_attempts,
        old_reauth_attempts=old_reauth_attempts,
        expired_refresh_receipts=expired_refresh_receipts,
    )


def run_auth_maintenance_if_due(
    *,
    now: datetime | None = None,
    monotonic_now: float | None = None,
) -> bool:
    global _last_auth_maintenance_monotonic

    current_monotonic = monotonic() if monotonic_now is None else monotonic_now

    with _auth_maintenance_lock:
        last_run = _last_auth_maintenance_monotonic
        if (
            last_run is not None
            and current_monotonic - last_run < AUTH_MAINTENANCE_INTERVAL_SECONDS
        ):
            return False

        run_auth_maintenance(now=now)
        _last_auth_maintenance_monotonic = current_monotonic
        return True
