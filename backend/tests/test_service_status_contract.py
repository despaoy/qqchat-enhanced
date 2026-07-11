import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.mark.asyncio
async def test_services_omit_platform_connection_checks(monkeypatch):
    from api import stats

    monkeypatch.setattr(stats, "_check_service", lambda port: False)

    payload = await stats.get_services()
    names = {item["name"] for item in payload["services"]}

    assert "QQ Adapter (NapCat)" not in names
    assert "NoneBot Bot" not in names
    assert not any(name.startswith("Platform ") for name in names)