"""Opt-in concurrency test, isolated schema; never modifies application tables."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from decimal import Decimal
import pytest
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from starlette.requests import Request
from app import main
from app.config import get_settings
from app.schemas import WorkspaceActionInput, PosShiftClose
from test_service_plans import scenario, USER

pytestmark=pytest.mark.skipif(os.environ.get('ACCOUNTING_INTEGRATION')!='1',reason='Opt-in isolated PostgreSQL concurrency test')


@pytest.mark.parametrize('first', ['sale','close'])
def test_sale_and_close_serialize_on_workspace_lock(monkeypatch, first):
    schema='accounting_test_'+uuid4().hex
    dsn=get_settings().database_url
    state,recipe=scenario()
    tenant=str(uuid4())
    user={**USER,'id':3,'tenant_id':tenant,'plan_code':'restaurant','staff_role':'pos_terminal'}
    operator={'id':2,'login':'cashier','display_name':'Cashier','staff_role':'cashier','access_permissions':{}}
    def connect():
        c=psycopg.connect(dsn,row_factory=dict_row)
        c.execute(f'SET search_path TO {schema}')
        c.execute("SET lock_timeout = '5s'")
        return c
    with psycopg.connect(dsn,autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA {schema}')
    try:
        with connect() as c:
            c.execute('CREATE TABLE operational_state (tenant_id text primary key, version int, payload jsonb, updated_at timestamptz)')
            c.execute('CREATE TABLE pos_shifts (id int primary key, tenant_id text, register_user_id int, branch_id text, opening_cash numeric, opened_by text, closed_by_user_id int, closing_cash numeric, expected_cash numeric, variance numeric, closed_at timestamptz)')
            c.execute('CREATE TABLE operational_events (tenant_id text,state_version int,actor_user_id int,actor_login text,actor_role text,branch_id text,action text,entity_type text,entity_id text,payload jsonb)')
            c.execute('INSERT INTO operational_state VALUES (%s,1,%s,now())',(tenant,Jsonb(state)))
            c.execute("INSERT INTO pos_shifts (id,tenant_id,register_user_id,branch_id,opening_cash,opened_by) VALUES (1,%s,3,'b1',0,'Cashier')",(tenant,))
        def workspace(c, tenant_id, for_update=False):
            return c.execute('SELECT * FROM operational_state WHERE tenant_id=%s'+(' FOR UPDATE' if for_update else ''),(str(tenant_id),)).fetchone()
        monkeypatch.setattr(main,'_workspace_row',workspace)
        monkeypatch.setattr(main,'_current_pos_operator',lambda *args:operator)
        monkeypatch.setattr(main,'_current_pos_shift',lambda c,u:c.execute('SELECT * FROM pos_shifts WHERE id=1 AND closed_at IS NULL').fetchone())
        monkeypatch.setattr(main,'_pos_shift_payload',lambda row:row)
        monkeypatch.setattr(main,'_authorize_staff_action',lambda *args:None)
        monkeypatch.setattr(main,'_check_origin',lambda *args:None)
        request=Request({'type':'http','method':'POST','headers':[(b'x-ashkana-client',b'pos')]})
        payload={'items':[{'id':recipe['id'],'quantity':1}], 'paymentMethod':'cash','received':1000,'requestId':uuid4().hex}
        command=WorkspaceActionInput(action='sale.create',payload=payload)
        started=Event()
        def invoke(kind, signal=False):
            with connect() as c:
                if signal: started.set()
                try:
                    if kind=='sale': return main.workspace_action(command,request,user,'cookie',c)
                    return main.close_pos_shift(PosShiftClose(closing_cash=Decimal('0')),request,'cookie',user,c)
                except HTTPException as error:
                    c.rollback()
                    return error.status_code
        # Hold the first transaction's tenant lock; the second request must wait.
        with connect() as first_connection, ThreadPoolExecutor(max_workers=1) as pool:
            workspace(first_connection,tenant,True)
            future=pool.submit(invoke,'close' if first=='sale' else 'sale',True)
            assert started.wait(5)
            if first=='sale': result=main.workspace_action(command,request,user,'cookie',first_connection)
            else: result=main.close_pos_shift(PosShiftClose(closing_cash=Decimal('0')),request,'cookie',user,first_connection)
            assert not future.done()
            first_connection.commit()
            second=future.result(timeout=10)
        with connect() as c:
            saved=workspace(c,tenant)['payload']
            shift=c.execute('SELECT * FROM pos_shifts WHERE id=1').fetchone()
        if first=='sale':
            sale=saved['sales'][0]
            assert shift['expected_cash']==Decimal(str(sale['total']))
            # Retry after the shift closed still returns the original receipt.
            replay=invoke('sale')
            assert replay['entity']['id']==result['entity']['id']
        else:
            assert second==409
            assert not saved['sales']
            assert shift['expected_cash']==0
    finally:
        with psycopg.connect(dsn,autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA {schema} CASCADE')
