from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Request, Response
from app import main

OWNER={'id':1,'role':'owner','tenant_id':'tenant-a','login':'admin'}
MANAGER={'id':2,'role':'branch','tenant_id':'tenant-a','branch_id':'b1','staff_role':'branch_manager','login':'manager'}
REQUEST=Request({'type':'http','headers':[(b'origin',b'http://127.0.0.1:8000')]})

class Connection:
    def __init__(self): self.calls=[]
    def execute(self, sql, params):
        self.calls.append((sql,params))
        return SimpleNamespace(fetchone=lambda:{'pin':'4821'})

@pytest.fixture
def employee(monkeypatch):
    value={'branch_id':'b1','staff_role':'cashier','can_reveal_pin':True}
    monkeypatch.setattr(main,'_employee_record',lambda conn,tenant,employee_id:value)
    monkeypatch.setattr(main,'_employee_pin_key',lambda:'test-key-only')
    return value

def test_owner_reveal_no_cache_and_audit_has_no_pin(employee):
    connection=Connection();response=Response()
    result=main.reveal_employee_pin(10,REQUEST,response,OWNER,connection)
    assert result=={'pin':'4821','requires_reset':False}
    assert response.headers['cache-control']=='no-store'
    assert connection.calls[0][1][-1]=='tenant-a'
    assert '4821' not in str(connection.calls[1])

def test_old_hash_requires_explicit_reset(employee):
    employee['can_reveal_pin']=False
    connection=Connection()
    assert main.reveal_employee_pin(10,REQUEST,Response(),OWNER,connection)['requires_reset']
    assert connection.calls==[]

@pytest.mark.parametrize('branch,role',[('b2','cashier'),('b1','branch_manager')])
def test_manager_cannot_reveal_other_branch_or_manager(employee,branch,role):
    employee.update(branch_id=branch,staff_role=role)
    connection=Connection()
    with pytest.raises(HTTPException) as denied: main.reveal_employee_pin(10,REQUEST,Response(),MANAGER,connection)
    assert denied.value.status_code==403 and connection.calls==[]

def test_cashier_cannot_reveal(employee):
    connection=Connection()
    with pytest.raises(HTTPException) as denied: main.reveal_employee_pin(10,REQUEST,Response(),{**MANAGER,'staff_role':'cashier'},connection)
    assert denied.value.status_code==403 and connection.calls==[]
