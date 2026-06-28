from __future__ import annotations

import getpass

from rich.console import Console
from rich.table import Table


def prompt_web_admin_password(console: Console) -> str:
    """Prompt for a web admin password without echoing it."""
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")

    if password != confirmation:
        console.print("[red]Passwords do not match.[/red]")
        raise SystemExit(1)

    return password


def create_web_admin_user(username: str, *, console: Console) -> None:
    """Create or update an active web admin user."""
    from fluxtuner.core import db
    from fluxtuner.web import auth

    clean_username = db.normalize_username(username)
    if not clean_username:
        console.print("[red]Username is required.[/red]")
        raise SystemExit(1)

    try:
        password_hash = auth.hash_password(prompt_web_admin_password(console))
    except auth.PasswordValidationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_profile_user_schema(conn)
        db.ensure_default_user(conn)

        existing_user = db.get_user_by_username(conn, clean_username)
        if existing_user is None:
            user_id = db.get_or_create_user(
                conn,
                clean_username,
                password_hash=password_hash,
                is_admin=True,
                is_active=True,
            )
            action = "created"
        else:
            user_id = int(existing_user["id"])
            conn.execute(
                """
                UPDATE users
                SET
                    password_hash = ?,
                    is_admin = 1,
                    is_active = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (password_hash, db.utc_now(), user_id),
            )
            action = "updated"

        db.ensure_default_profile(conn, user_id=user_id)
        conn.commit()

    console.print(f"[green]Web admin user {clean_username!r} {action}.[/green]")


def print_web_users(*, console: Console) -> None:
    """Print web users without exposing password hashes."""
    from fluxtuner.core import db

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_profile_user_schema(conn)
        users = db.list_users(conn)

    table = Table(title="FluxTuner web users")
    table.add_column("Username")
    table.add_column("Display name")
    table.add_column("Admin")
    table.add_column("Active")
    table.add_column("Created")
    table.add_column("Updated")

    for user in users:
        table.add_row(
            str(user["username"]),
            str(user["display_name"]),
            "yes" if user["is_admin"] else "no",
            "yes" if user["is_active"] else "no",
            str(user["created_at"]),
            str(user["updated_at"]),
        )

    console.print(table)


def set_web_user_password(username: str, *, console: Console) -> None:
    """Set a web user's password without printing secrets."""
    from fluxtuner.core import db
    from fluxtuner.web import auth

    clean_username = db.normalize_username(username)
    if not clean_username:
        console.print("[red]Username is required.[/red]")
        raise SystemExit(1)

    try:
        password_hash = auth.hash_password(prompt_web_admin_password(console))
    except auth.PasswordValidationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_profile_user_schema(conn)

        user = db.get_user_by_username(conn, clean_username)
        if user is None:
            console.print(f"[red]Web user {clean_username!r} does not exist.[/red]")
            raise SystemExit(1)

        conn.execute(
            """
            UPDATE users
            SET
                password_hash = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (password_hash, db.utc_now(), int(user["id"])),
        )
        conn.execute(
            """
            UPDATE web_sessions
            SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            (db.utc_now(), int(user["id"])),
        )
        conn.commit()

    console.print(f"[green]Password updated for web user {clean_username!r}.[/green]")


def deactivate_web_user(username: str, *, console: Console) -> None:
    """Deactivate a web user and revoke active sessions."""
    from fluxtuner.core import db

    clean_username = db.normalize_username(username)
    if not clean_username:
        console.print("[red]Username is required.[/red]")
        raise SystemExit(1)

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_profile_user_schema(conn)

        user = db.get_user_by_username(conn, clean_username)
        if user is None:
            console.print(f"[red]Web user {clean_username!r} does not exist.[/red]")
            raise SystemExit(1)

        now = db.utc_now()
        conn.execute(
            """
            UPDATE users
            SET
                is_active = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (now, int(user["id"])),
        )
        conn.execute(
            """
            UPDATE web_sessions
            SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            (now, int(user["id"])),
        )
        conn.commit()

    console.print(f"[green]Web user {clean_username!r} deactivated.[/green]")


def handle_web_user_command(command: list[str], *, console: Console) -> bool:
    """Handle web user management subcommands."""
    if command == ["web", "users", "list"]:
        print_web_users(console=console)
        return True

    if len(command) == 4 and command[:3] == ["web", "users", "create-admin"]:
        create_web_admin_user(command[3], console=console)
        return True

    if len(command) == 4 and command[:3] == ["web", "users", "set-password"]:
        set_web_user_password(command[3], console=console)
        return True

    if len(command) == 4 and command[:3] == ["web", "users", "deactivate"]:
        deactivate_web_user(command[3], console=console)
        return True

    if command[:2] == ["web", "users"]:
        console.print(
            "[red]Usage: fluxtuner web users "
            "{list|create-admin USERNAME|set-password USERNAME|deactivate USERNAME}[/red]"
        )
        raise SystemExit(1)

    return False
