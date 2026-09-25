"""M2.3 real PostgreSQL backup creation when pg_dump is available."""

import shutil
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from research_agent.application.backup_creation_service import BackupCreationService
from research_agent.application.migrations import run_migrations
from research_agent.config.settings import get_settings
from research_agent.domain.backup import BackupManifest

SOURCE_REVISION = "316c90bf1816743ce73571e907b5c24e4da6cdec"


@pytest.mark.skipif(shutil.which("pg_dump") is None, reason="pg_dump is not installed")
def test_real_pg_dump_backup_set_contains_manifest_and_dump(tmp_path):
    base_url = make_url(get_settings().database_url)
    if base_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("real backup integration requires local PostgreSQL")
    database = "backup_creation_test_" + uuid4().hex
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    created = False
    isolated_url = base_url.set(database=database)
    isolated = create_engine(isolated_url)
    try:
        try:
            with admin.connect() as conn:
                conn.exec_driver_sql(f'CREATE DATABASE "{database}"')
            created = True
        except SQLAlchemyError as exc:
            pytest.skip(f"cannot create disposable database: {exc}")
        run_migrations(isolated)
        task_id = uuid4()
        with isolated.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO research_tasks (
                        id, title, objective, status, brief, plan, created_at, updated_at
                    )
                    VALUES (:id, 'Backup creation', 'Verify pg_dump.', 'active',
                            '{}'::jsonb, '{}'::jsonb, now(), now())
                    """
                ),
                {"id": task_id},
            )
        result = BackupCreationService(isolated).create(
            tmp_path / "backup-set",
            application_version="0.1.0",
            source_revision=SOURCE_REVISION,
        )
        assert result.dump_path.is_file()
        assert result.dump_path.stat().st_size > 0
        manifest = BackupManifest.model_validate_json(result.manifest_path.read_text())
        assert manifest.integrity.dump_sha256 == result.manifest.integrity.dump_sha256
        manifest_text = result.manifest_path.read_text()
        assert "postgresql+psycopg://" not in manifest_text
        if base_url.password:
            assert base_url.password not in manifest_text
    finally:
        isolated.dispose()
        if created:
            with admin.connect() as conn:
                conn.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
        admin.dispose()
