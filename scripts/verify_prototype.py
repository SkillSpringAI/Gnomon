"""Verify fresh migrations and a real HTTP server using a disposable local database."""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from research_agent.application.migrations import migration_files, run_migrations
from research_agent.config.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serve", action="store_true", help="Keep the disposable app for browser QA"
    )
    args = parser.parse_args()
    base_url = make_url(get_settings().database_url)
    if base_url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Prototype verification requires a local PostgreSQL server")
    # The name is generated here, never accepted as an argument or taken from settings.
    database = "gnomon_verify_" + uuid4().hex
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    isolated_url = base_url.set(database=database)
    isolated = create_engine(isolated_url)
    process = None
    created = False
    with tempfile.TemporaryFile(mode="w+b") as log:
        try:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
            created = True
            applied = run_migrations(isolated)
            assert applied == [path.name for path in migration_files()]
            assert not run_migrations(isolated), "Migration rerun must be a no-op"
            print(
                f"Fresh database: {len(applied)} migrations applied; rerun is a no-op.", flush=True
            )
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            env = os.environ | {
                "DATABASE_URL": isolated_url.render_as_string(hide_password=False),
                "PERSISTENCE_BACKEND": "postgres",
                "LLM_PROVIDER": "stub",
                "ENVIRONMENT": "test",
            }

            def start():
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "research_agent.api.app:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    stdout=log,
                    stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                return child

            def ready(client):
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    assert process.poll() is None, "Server exited during startup"
                    try:
                        if client.get("/health").status_code == 200:
                            return
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                raise RuntimeError("Server did not become ready")

            def stop():
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)

            def json_response(response):
                response.raise_for_status()
                return response.json()

            process = start()
            origin = f"http://127.0.0.1:{port}"
            with httpx.Client(base_url=origin, timeout=10, trust_env=False) as client:
                ready(client)
                task = json_response(
                    client.post(
                        "/investigations",
                        json={
                            "title": "Fresh prototype verification",
                            "objective": "Verify persisted cycles.",
                        },
                    )
                )["task"]
                prefix = f"/investigations/{task['id']}"
                json_response(
                    client.patch(
                        f"{prefix}/status",
                        json={
                            "expected_status": "active",
                            "status": "paused",
                        },
                    )
                )
                assert client.post(f"{prefix}/cycles/1/run", json={}).status_code == 409
                json_response(
                    client.patch(
                        f"{prefix}/status",
                        json={
                            "expected_status": "paused",
                            "status": "active",
                        },
                    )
                )
                for number in (1, 2):
                    if number == 2:
                        json_response(client.post(f"{prefix}/cycles"))
                    result = json_response(client.post(f"{prefix}/cycles/{number}/run", json={}))
                    cycle = result["task"]["cycles"][number - 1]
                    assert cycle["status"] == "completed" and len(cycle["evidence_ids"]) == 2
                    assert cycle["unresolved_objectives"] and cycle["claim_ids"]
                json_response(client.post(f"{prefix}/cycles"))
                blocked = json_response(
                    client.post(
                        f"{prefix}/cycles/3/run",
                        json={
                            "scenario": "unresponsive",
                        },
                    )
                )["task"]["cycles"][2]
                assert blocked["status"] == "blocked" and blocked["unresolved_objectives"]
                assert blocked["evidence_ids"] == []
                before = json_response(client.get(f"{prefix}/report"))
                assert len(before["sources"]) == 4
                stop()
                process = start()
                ready(client)
                assert json_response(client.get(f"{prefix}/report")) == before
                assert client.get(f"{prefix}/workspace").status_code == 200
                print(
                    "Real HTTP: lifecycle, two cycles, blocked outcome "
                    "and restart persistence passed.",
                    flush=True,
                )
                if args.serve:
                    browser_task = json_response(
                        client.post(
                            "/investigations",
                            json={
                                "title": "Browser workflow verification",
                                "objective": "Exercise workspace controls.",
                            },
                        )
                    )["task"]
                    print(
                        f"Browser QA: {origin}/investigations/{browser_task['id']}/workspace",
                        flush=True,
                    )
                    print("Press Ctrl+C to stop and remove the disposable database.", flush=True)
                    try:
                        while process.poll() is None:
                            time.sleep(0.5)
                    except KeyboardInterrupt:
                        pass
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            isolated.dispose()
            if created:
                with admin.connect() as connection:
                    connection.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
                print("Removed the disposable verification database.", flush=True)
            admin.dispose()


if __name__ == "__main__":
    main()
