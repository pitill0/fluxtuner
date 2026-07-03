# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Path, Request, Response

from fluxtuner.core import db
from fluxtuner.web import admin_actions, password_change_actions
from fluxtuner.web import context as web_context
from fluxtuner.web import guards as web_guards

AUTH_REQUIRED_DETAIL = "Authentication required."
ADMIN_REQUIRED_DETAIL = "Administrator access required."
CSRF_ERROR_DETAIL = "CSRF token is missing or invalid."
FIELD_TOO_LONG_DETAIL = "One or more fields exceed the maximum allowed length."
MAX_USERNAME_LENGTH = 80
MAX_DISPLAY_NAME_LENGTH = 120

router = APIRouter()
required_body = Body(...)


def require_csrf(request: Request) -> None:
    web_guards.require_csrf(
        request,
        csrf_error_detail=CSRF_ERROR_DETAIL,
    )


def require_admin_user(request: Request) -> dict[str, Any]:
    return web_guards.require_admin_user(
        request,
        auth_required_detail=AUTH_REQUIRED_DETAIL,
        admin_required_detail=ADMIN_REQUIRED_DETAIL,
    )


@router.get("/api/admin/password-change-requests")
def admin_list_password_change_requests(request: Request) -> dict[str, Any]:
    require_admin_user(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return password_change_actions.list_password_change_requests_payload(conn)


@router.post("/api/admin/password-change-requests/{request_id}/approve")
def admin_approve_password_change_request(
    request: Request,
    request_id: int = Path(..., ge=1),
) -> dict[str, Any]:
    admin_user = require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return password_change_actions.approve_password_change_request_payload(
            conn,
            request_id,
            resolved_by_user_id=int(admin_user["id"]),
        )


@router.post("/api/admin/password-change-requests/{request_id}/reject")
def admin_reject_password_change_request(
    request: Request,
    request_id: int = Path(..., ge=1),
) -> dict[str, str]:
    admin_user = require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return password_change_actions.reject_password_change_request_payload(
            conn,
            request_id,
            resolved_by_user_id=int(admin_user["id"]),
        )


@router.get("/api/admin/users")
def admin_list_users(request: Request) -> dict[str, Any]:
    require_admin_user(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.list_users_payload(conn)


@router.post("/api/admin/users")
def admin_create_user(
    request: Request,
    payload: dict[str, Any] = required_body,
) -> dict[str, Any]:
    require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.create_user_payload(
            conn,
            payload,
            max_username_length=MAX_USERNAME_LENGTH,
            max_display_name_length=MAX_DISPLAY_NAME_LENGTH,
            field_too_long_detail=FIELD_TOO_LONG_DETAIL,
        )


@router.post("/api/admin/users/{username}/password")
def admin_set_user_password(
    username: str,
    request: Request,
    payload: dict[str, Any] = required_body,
) -> dict[str, Any]:
    require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.set_user_password_payload(conn, username, payload)


@router.post("/api/admin/users/{username}/deactivate")
def admin_deactivate_user(username: str, request: Request) -> dict[str, Any]:
    admin_user = require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.set_user_approval_payload(
            conn,
            username,
            approval_status=db.APPROVAL_DISABLED,
            reviewed_by_user_id=int(admin_user["id"]),
            revoke_sessions=True,
            protect_last_admin=True,
        )


@router.post("/api/admin/users/{username}/activate")
def admin_activate_user(username: str, request: Request) -> dict[str, Any]:
    admin_user = require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.set_user_approval_payload(
            conn,
            username,
            approval_status=db.APPROVAL_APPROVED,
            reviewed_by_user_id=int(admin_user["id"]),
            revoke_sessions=False,
            protect_last_admin=False,
        )


@router.delete("/api/admin/users/{username}")
def admin_delete_user(username: str, request: Request) -> Response:
    admin_user = require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        admin_actions.delete_user(conn, username, admin_user_id=int(admin_user["id"]))

    return Response(status_code=204)


@router.post("/api/admin/users/{username}/approve")
def admin_approve_user(username: str, request: Request) -> dict[str, Any]:
    admin_user = require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.set_user_approval_payload(
            conn,
            username,
            approval_status=db.APPROVAL_APPROVED,
            reviewed_by_user_id=int(admin_user["id"]),
            revoke_sessions=False,
            protect_last_admin=False,
        )


@router.post("/api/admin/users/{username}/reject")
def admin_reject_user(username: str, request: Request) -> dict[str, Any]:
    admin_user = require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.set_user_approval_payload(
            conn,
            username,
            approval_status=db.APPROVAL_REJECTED,
            reviewed_by_user_id=int(admin_user["id"]),
            revoke_sessions=True,
            protect_last_admin=True,
        )


@router.post("/api/admin/users/{username}/admin")
def admin_grant_admin(username: str, request: Request) -> dict[str, Any]:
    require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.set_user_admin_payload(
            conn,
            username,
            is_admin=True,
            protect_last_admin=False,
        )


@router.delete("/api/admin/users/{username}/admin")
def admin_revoke_admin(username: str, request: Request) -> dict[str, Any]:
    require_admin_user(request)
    require_csrf(request)

    with db.connect() as conn:
        web_context.ensure_web_schema(conn)
        return admin_actions.set_user_admin_payload(
            conn,
            username,
            is_admin=False,
            protect_last_admin=True,
        )
