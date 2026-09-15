"""Build a wheel and verify a clean base installation outside the checkout."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from uuid import uuid4

PROBE = r'''
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

import research_agent
from research_agent.api.app import create_app
from research_agent.application.migrations import (
    migration_checksum, migration_files, run_migrations,
)
from research_agent.config.settings import get_settings

assert Path(research_agent.__file__).is_relative_to(Path(sys.prefix))
assert importlib.util.find_spec("boto3") is None, "Base installation unexpectedly requires AWS"
resources = migration_files()
expected = json.loads(Path("expected.json").read_text())
assert {path.name: migration_checksum(path) for path in resources} == expected
print(f"Installed wheel: {len(resources)} migration resources match source checksums", flush=True)

os.environ["PERSISTENCE_BACKEND"] = "memory"
get_settings.cache_clear()
with TestClient(create_app()) as client, TestClient(create_app()) as isolated:
    assert client.get("/health").status_code == 200
    task = client.post("/investigations", json={"title": "Wheel", "objective": "Verify wheel."})
    assert task.status_code == 201
    task_id = task.json()["task"]["id"]
    assert client.get(f"/investigations/{task_id}").status_code == 200
    assert client.post(f"/investigations/{task_id}/cycles/1/start").status_code == 200
    assert isolated.get(f"/investigations/{task_id}").status_code == 404
    assert client.get("/provider/status").json()["provider"] == "stub"
print("Base wheel: configured memory API and provider status pass without AWS", flush=True)

if "WHEEL_TEST_DB" in os.environ:
    db = create_engine(os.environ["WHEEL_TEST_DB"])
    try:
        with tempfile.TemporaryDirectory() as folder:
            baseline = Path(folder)
            for resource in resources[:-1]:
                (baseline / resource.name).write_bytes(resource.read_bytes())
            barrier = Barrier(2)
            def install():
                barrier.wait(timeout=10)
                return run_migrations(db, baseline)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(install) for _ in range(2)]
                applied = [name for future in futures for name in future.result(timeout=30)]
            assert sorted(applied) == [path.name for path in resources[:-1]]
            fixture = uuid4()
            with db.begin() as connection:
                connection.execute(text("""
                    INSERT INTO research_tasks
                    (id, title, objective, status, brief, plan, created_at, updated_at)
                    VALUES (:id, 'Wheel upgrade', 'Retain state', 'active',
                            '{}', '{}', now(), now())
                """), {"id": fixture})
            assert run_migrations(db) == [resources[-1].name]
            assert run_migrations(db) == []
            with db.connect() as connection:
                assert connection.scalar(text("SELECT title FROM research_tasks WHERE id=:id"),
                                         {"id": fixture}) == "Wheel upgrade"
            for resource in resources:
                (baseline / resource.name).write_bytes(resource.read_bytes())
            first = baseline / resources[0].name
            first.write_bytes(first.read_bytes() + b"\n-- changed historical migration\n")
            try:
                run_migrations(db, baseline)
            except RuntimeError as error:
                assert "Applied migration content changed" in str(error)
            else:
                raise AssertionError("Historical migration drift was accepted")
        os.environ["DATABASE_URL"] = os.environ["WHEEL_TEST_DB"]
        os.environ["PERSISTENCE_BACKEND"] = "postgres"
        get_settings.cache_clear()
        # database module was initialized for the same disposable DB by the parent.
        with TestClient(create_app()) as client:
            task = client.post("/investigations", json={"title": "Wheel DB", "objective": "Draft."})
            assert task.status_code == 201
            task_id = task.json()["task"]["id"]
            draft = client.post(f"/investigations/{task_id}/report/draft")
            assert draft.status_code == 200, draft.text
            assert client.get(f"/investigations/{task_id}/workspace").status_code == 200
        print("Installed wheel: schema, upgrade, rerun, drift rejection and draft pass",
              flush=True)
    finally:
        db.dispose()
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", action="store_true", help="Verify a disposable PostgreSQL DB")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["LLM_PROVIDER"] = "stub"
    environment["LLM_MAX_DRAFTS_PER_TASK"] = "20"
    environment["PERSISTENCE_BACKEND"] = "memory"
    admin = None
    database = "wheel_verify_" + uuid4().hex
    created = False
    try:
        if args.database:
            from sqlalchemy import create_engine
            from sqlalchemy.engine import make_url

            from research_agent.config.settings import get_settings

            url = make_url(get_settings().database_url)
            if url.host not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("Wheel verification requires local PostgreSQL")
            admin = create_engine(url, isolation_level="AUTOCOMMIT")
            with admin.connect() as connection:
                connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
            created = True
            isolated_url = url.set(database=database).render_as_string(hide_password=False)
            environment["WHEEL_TEST_DB"] = isolated_url
            environment["DATABASE_URL"] = isolated_url
        with tempfile.TemporaryDirectory(prefix="gnomon-wheel-") as folder:
            work = Path(folder)
            subprocess.run(
                [sys.executable, "-m", "pip", "wheel", "--no-deps", str(root), "-w", str(work)],
                check=True,
                cwd=work,
            )
            wheel = next(work.glob("research_agent-*.whl"))
            destination = work / "venv"
            venv.EnvBuilder(with_pip=True).create(destination)
            python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run([str(python), "-m", "pip", "install", str(wheel)], check=True, cwd=work)
            subprocess.run([str(python), "-m", "pip", "check"], check=True, cwd=work)
            manifest = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (root / "src/research_agent/migrations").glob("*.sql")
            }
            if not manifest:
                raise RuntimeError("Source migration inventory is empty")
            (work / "expected.json").write_text(json.dumps(manifest), encoding="utf-8")
            (work / "probe.py").write_text(PROBE, encoding="utf-8")
            subprocess.run([str(python), "probe.py"], check=True, cwd=work, env=environment)
    finally:
        if admin is not None:
            if created:
                with admin.connect() as connection:
                    connection.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
                print("Removed disposable wheel verification database", flush=True)
            admin.dispose()


if __name__ == "__main__":
    main()
