from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import custody, main
from app.workspace import WorkspaceError, apply_action
from test_custody import setup, send, accept, execute, RECEIVER, MANAGER, COOK

CASHIER = {**RECEIVER, 'shift_id': 20}


def exhausted():
    state, batch, recipe = setup()
    accept(state, send(state, batch))
    lot = batch['servingLots'][0]
    execute(state, CASHIER, 'sale.create', items=[{'id':recipe['id'],'quantity':4}], paymentMethod='card')
    assert custody.lot_available(lot) == 0
    return state, batch, recipe, lot


def request(state, batch, lot, **extra):
    payload = {'batchId':batch['id'], 'lotId':lot['id'], 'weight':.5, 'reason':'Found two extra portions', 'requestId':str(uuid4()), **extra}
    return payload, apply_action(state, CASHIER, 'pos.serving.surplus', payload)[1]


@pytest.mark.parametrize('decision,expected', [('approve',.5),('reject',0)])
def test_surplus_requires_manager_and_never_consumes_ingredients(decision, expected):
    state, batch, recipe, lot = exhausted()
    raw = deepcopy(state['logisticsState']['branchStocks'])
    ledger = deepcopy(state['logisticsState']['stockLedger'])
    kitchen = custody.kitchen_balance(batch)
    payload, doc_id = request(state,batch,lot)
    assert custody.lot_available(lot) == 0
    with pytest.raises(WorkspaceError):
        execute(state,CASHIER,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    assert apply_action(state,CASHIER,'pos.serving.surplus',payload)[1] == doc_id
    with pytest.raises(WorkspaceError):
        request(state,batch,lot)
    with pytest.raises(WorkspaceError):
        execute(state,CASHIER,'custody.review',documentId=doc_id,decision=decision,reason='Checked')
    execute(state,MANAGER,'custody.review',documentId=doc_id,decision=decision,reason='Checked portions')
    assert custody.lot_available(lot) == expected
    doc = next(doc for doc in state['logisticsState']['custodyDocuments'] if doc['id']==doc_id)
    assert doc['actor']['id']==CASHIER['id'] and doc['shiftId']==20
    assert doc['reviewedBy']['id']==MANAGER['id']
    assert state['logisticsState']['branchStocks']==raw
    assert state['logisticsState']['stockLedger']==ledger
    assert custody.kitchen_balance(batch)==kitchen
    with pytest.raises(WorkspaceError):
        execute(state,MANAGER,'custody.review',documentId=doc_id,decision='approve',reason='Again')
    if decision=='approve':
        execute(state,CASHIER,'sale.create',items=[{'id':recipe['id'],'quantity':2}],paymentMethod='card')
        assert custody.lot_available(lot)==0
        assert state['logisticsState']['branchStocks']==raw


@pytest.mark.parametrize('actor', [COOK,{**CASHIER,'shift_id':None},{**CASHIER,'staff_role':'waiter'}, {**CASHIER,'branch_id':'b2'}, {**CASHIER,'plan_code':'restaurant'}])
def test_surplus_permissions(actor):
    state,batch,_,lot=exhausted()
    with pytest.raises(WorkspaceError):
        execute(state,actor,'pos.serving.surplus',batchId=batch['id'],lotId=lot['id'],weight=.5,reason='Extra portions')


@pytest.mark.parametrize('weight', [0,-1,float('nan'),float('inf'),10001])
def test_invalid_surplus_weight(weight):
    state,batch,_,lot=exhausted()
    with pytest.raises(WorkspaceError):
        request(state,batch,lot,weight=weight)
    assert custody.lot_available(lot)==0


def test_unaccepted_lot_cannot_be_corrected_as_surplus():
    state,batch,_,lot=exhausted()
    lot['legacy']=True
    with pytest.raises(WorkspaceError):
        request(state,batch,lot)


def test_context_includes_zero_accepted_stock_and_scopes_branch(monkeypatch):
    state,batch,_,lot=exhausted()
    foreign=deepcopy(batch);foreign.update(id='foreign',branchId='b2')
    state['logisticsState']['batches'].append(foreign)
    monkeypatch.setattr(main,'_current_pos_operator',lambda *args:CASHIER)
    monkeypatch.setattr(main,'_current_pos_shift',lambda *args:{'id':20})
    monkeypatch.setattr(main,'_workspace_row',lambda *args:{'payload':state})
    result=main.pos_serving_surpluses(None,{**CASHIER,'tenant_id':'tenant'},None)
    assert len(result['lots'])==1 and result['lots'][0]['id']==lot['id']
    assert result['lots'][0]['availableWeight']==0
    assert 'cost' not in result['lots'][0]
    with pytest.raises(HTTPException):
        main.pos_serving_surpluses(None,{**CASHIER,'tenant_id':'tenant','plan_code':'restaurant'},None)
