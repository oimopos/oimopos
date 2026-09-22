import pytest
from fastapi import HTTPException
from app.main import _authorize_staff_action, _normalized_permissions


@pytest.mark.parametrize('action', ['sale.create', 'sale.refund', 'pos.order.save', 'pos.order.remove', 'pos.order.status', 'pos.customer.upsert', 'pos.cash.movement'])
def test_production_cannot_sell_even_with_old_full_permissions(action):
    user = {'role': 'branch', 'staff_role': 'production', 'access_permissions': {'posAccess': True, 'posRefunds': True, 'posCash': True}}
    with pytest.raises(HTTPException) as error:
        _authorize_staff_action(user, action)
    assert error.value.status_code == 403


def test_production_terminal_and_supply_available_for_existing_staff():
    permissions = _normalized_permissions('production', {'production': True})
    assert permissions['posAccess'] and permissions['posSupply']
    assert not permissions['posCash'] and not permissions['posRefunds']
    user = {'role': 'branch', 'staff_role': 'production', 'register_id': 'terminal', 'access_permissions': {'production': True}}
    for action in ['batch.release', 'batch.transfer', 'supply.create', 'custody.writeoff']:
        _authorize_staff_action(user, action)


def test_production_has_no_admin_access_even_with_old_grants():
    from app.main import _has_admin_access
    user = {'role': 'branch', 'staff_role': 'production', 'access_permissions': {'production': True, 'employees': True, 'settings': True, 'finance': True}}
    assert not _has_admin_access(user)
    permissions = _normalized_permissions('production', user['access_permissions'])
    assert permissions['production'] and permissions['posAccess']
    assert not permissions['employees'] and not permissions['settings'] and not permissions['finance']


def test_existing_production_admin_session_cannot_read_workspace():
    from app import main
    from starlette.requests import Request
    from types import SimpleNamespace
    class Connection:
        def execute(self, *args):
            return SimpleNamespace(fetchone=lambda: {'role': 'branch', 'staff_role': 'production'})
    request = Request({'type': 'http', 'path': '/api/v1/workspace', 'headers': [(b'x-ashkana-client', b'admin')]})
    with pytest.raises(HTTPException) as error:
        main.current_user(request, 'old-admin-session', None, Connection())
    assert error.value.status_code == 403
