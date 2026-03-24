from __future__ import annotations

import re
from pathlib import Path


REVISION_PATTERN = re.compile(r'^revision:\s*str\s*=\s*"([^"]+)"', re.MULTILINE)
ALEMBIC_VERSION_MAX_LENGTH = 32


def test_alembic_revision_ids_fit_version_table_limit() -> None:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    revision_ids: list[tuple[str, str]] = []

    for path in sorted(versions_dir.glob("*.py")):
        match = REVISION_PATTERN.search(path.read_text(encoding="utf-8"))
        if match is None:
            continue
        revision_ids.append((path.name, match.group(1)))

    assert revision_ids, "Expected at least one Alembic revision file."
    too_long = [(name, revision_id) for name, revision_id in revision_ids if len(revision_id) > ALEMBIC_VERSION_MAX_LENGTH]
    assert too_long == []
