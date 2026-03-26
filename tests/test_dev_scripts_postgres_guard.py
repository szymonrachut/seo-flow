from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def get_powershell_executable() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is not available in PATH.", allow_module_level=False)
    return executable


def run_dev_script(command: str, workdir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    powershell_executable = get_powershell_executable()
    project_root = Path(__file__).resolve().parents[1]
    args = [powershell_executable]
    if os.name == "nt":
        args.extend(["-ExecutionPolicy", "Bypass"])
    args.extend(
        [
            "-File",
            str(project_root / "scripts" / "dev.ps1"),
            "-Command",
            command,
        ]
    )
    args.extend(extra_args)
    completed = subprocess.run(
        args,
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return completed


def write_env_file(
    path: Path,
    *,
    user: str = "postgres",
    password: str = "postgres",
    database: str = "seo_crawler",
    host: str = "localhost",
    port: str = "5432",
    database_url: str | None = None,
) -> None:
    effective_database_url = database_url or f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
    path.write_text(
        "\n".join(
            [
                f"POSTGRES_USER={user}",
                f"POSTGRES_PASSWORD={password}",
                f"POSTGRES_DB={database}",
                f"POSTGRES_HOST={host}",
                f"POSTGRES_PORT={port}",
                f"DATABASE_URL={effective_database_url}",
                "LOG_LEVEL=INFO",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def test_db_sync_env_restores_credentials_from_trusted_lock(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    write_env_file(
        env_path,
        password="p@ss:one",
        database_url="postgresql+psycopg://postgres:wrong@localhost:5432/old_db",
    )

    run_dev_script("db-sync-env", tmp_path)

    lock_path = tmp_path / ".local" / "postgres" / "credentials.env"
    assert not lock_path.exists()

    first_sync_env = read_env_file(env_path)
    assert first_sync_env["POSTGRES_PASSWORD"] == "p@ss:one"
    assert first_sync_env["POSTGRES_DB"] == "seo_crawler"
    assert first_sync_env["DATABASE_URL"] == "postgresql+psycopg://postgres:wrong@localhost:5432/old_db"

    run_dev_script("db-refresh-lock", tmp_path)
    assert lock_path.exists()

    refreshed_lock = read_env_file(lock_path)
    assert refreshed_lock["LOCK_TRUSTED"] == "1"
    assert refreshed_lock["POSTGRES_PASSWORD"] == "p@ss:one"
    assert refreshed_lock["POSTGRES_DB"] == "seo_crawler"

    refreshed_env = read_env_file(env_path)
    assert refreshed_env["DATABASE_URL"] == "postgresql+psycopg://postgres:p%40ss%3Aone@localhost:5432/seo_crawler"

    write_env_file(
        env_path,
        password="new-pass",
        database="other_db",
        host="127.0.0.1",
        port="5544",
        database_url="postgresql+psycopg://postgres:new-pass@127.0.0.1:5544/other_db",
    )

    run_dev_script("db-sync-env", tmp_path)

    second_sync_env = read_env_file(env_path)
    assert second_sync_env["POSTGRES_PASSWORD"] == "p@ss:one"
    assert second_sync_env["POSTGRES_DB"] == "seo_crawler"
    assert second_sync_env["POSTGRES_HOST"] == "127.0.0.1"
    assert second_sync_env["POSTGRES_PORT"] == "5544"
    assert second_sync_env["DATABASE_URL"] == "postgresql+psycopg://postgres:p%40ss%3Aone@127.0.0.1:5544/seo_crawler"

    locked_values = read_env_file(lock_path)
    assert locked_values["LOCK_TRUSTED"] == "1"
    assert locked_values["POSTGRES_PASSWORD"] == "p@ss:one"
    assert locked_values["POSTGRES_DB"] == "seo_crawler"


def test_db_refresh_lock_adopts_current_env_credentials(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    write_env_file(env_path, password="old-pass")

    write_env_file(
        env_path,
        password="next@pass",
        database="seo_next",
        host="db.local",
        port="6543",
    )

    run_dev_script("db-refresh-lock", tmp_path)
    refreshed_env = read_env_file(env_path)
    refreshed_lock = read_env_file(tmp_path / ".local" / "postgres" / "credentials.env")

    assert refreshed_env["POSTGRES_PASSWORD"] == "next@pass"
    assert refreshed_env["POSTGRES_DB"] == "seo_next"
    assert refreshed_env["POSTGRES_HOST"] == "db.local"
    assert refreshed_env["POSTGRES_PORT"] == "6543"
    assert refreshed_env["DATABASE_URL"] == "postgresql+psycopg://postgres:next%40pass@db.local:6543/seo_next"

    assert refreshed_lock["LOCK_TRUSTED"] == "1"
    assert refreshed_lock["POSTGRES_PASSWORD"] == "next@pass"
    assert refreshed_lock["POSTGRES_DB"] == "seo_next"


def test_trusted_lock_changes_only_on_explicit_refresh(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    lock_path = tmp_path / ".local" / "postgres" / "credentials.env"

    write_env_file(env_path, password="stable-pass")
    run_dev_script("db-refresh-lock", tmp_path)

    initial_lock = read_env_file(lock_path)
    assert initial_lock["LOCK_TRUSTED"] == "1"
    assert initial_lock["POSTGRES_PASSWORD"] == "stable-pass"

    write_env_file(env_path, password="accidental-pass")
    run_dev_script("db-sync-env", tmp_path)

    synced_env = read_env_file(env_path)
    synced_lock = read_env_file(lock_path)
    assert synced_env["POSTGRES_PASSWORD"] == "stable-pass"
    assert synced_lock["POSTGRES_PASSWORD"] == "stable-pass"

    write_env_file(env_path, password="next-pass")
    run_dev_script("db-refresh-lock", tmp_path)

    refreshed_lock = read_env_file(lock_path)
    assert refreshed_lock["POSTGRES_PASSWORD"] == "next-pass"


def test_init_worktree_env_generates_isolated_ports_and_paths(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    frontend_env_path = tmp_path / "frontend" / ".env.local"
    frontend_env_path.parent.mkdir(parents=True, exist_ok=True)

    write_env_file(env_path)
    frontend_env_path.write_text("VITE_API_BASE_URL=http://localhost:8000\n", encoding="utf-8")

    run_dev_script("init-worktree-env", tmp_path)

    env_values = read_env_file(env_path)
    frontend_values = read_env_file(frontend_env_path)
    state_values = read_env_file(tmp_path / ".local" / "worktree" / "instance.env")

    assert env_values["WORKTREE_INSTANCE_ID"]
    assert env_values["COMPOSE_PROJECT_NAME"].startswith("seo-flow-")
    assert env_values["WORKTREE_STATE_DIR"] == ".local/worktree"
    assert env_values["POSTGRES_PORT"] != "5432"
    assert env_values["API_PORT"] != "8000"
    assert env_values["POSTGRES_DB"].startswith("seo_")
    assert env_values["GSC_CLIENT_SECRETS_PATH"] == ".local/worktree/gsc/credentials.json"
    assert env_values["GSC_TOKEN_PATH"] == ".local/worktree/gsc/token.json"
    assert env_values["GSC_OAUTH_STATE_PATH"] == ".local/worktree/gsc/oauth_state.json"
    assert frontend_values["VITE_API_BASE_URL"] == f"http://127.0.0.1:{env_values['API_PORT']}"
    assert state_values["WORKTREE_INSTANCE_ID"] == env_values["WORKTREE_INSTANCE_ID"]
    assert state_values["POSTGRES_PORT"] == env_values["POSTGRES_PORT"]
