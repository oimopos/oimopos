from copy import deepcopy
from uuid import uuid4
import pytest
from app import custody, production_shifts, shift_reconciliation
from app.workspace import apply_action, WorkspaceError, visible_state
from test_custody import setup, send, accept, execute, RECEIVER, MANAGER
from test_terminal_production import USER, scenario


def counts(state):
    return [{'id':r['id'], 'expectedQuantity':r['quantity'], 'actualQuantity':r['quantity']} for r in production_shifts.ingredient_stocks(state,'b1')]


def accepted():
    state,batch,recipe=setup()
    accept(state,send(state,batch))
    return state,batch,recipe


def test_sale_retry_is_idempotent_and_payload_or_actor_cannot_change():
    state,batch,recipe=accepted()
    payload={'items':[{'id':recipe['id'],'quantity':1}], 'paymentMethod':'card', 'requestId':str(uuid4())}
    result=apply_action(state,RECEIVER,'sale.create',payload)
    snapshot=deepcopy(state)
    assert apply_action(state,RECEIVER,'sale.create',payload)==result
    assert state==snapshot
    with pytest.raises(WorkspaceError): apply_action(state,RECEIVER,'sale.create',{**payload,'paymentMethod':'cash'})
    with pytest.raises(WorkspaceError): apply_action(state,{**RECEIVER,'id':999},'sale.create',payload)
    with pytest.raises(WorkspaceError): apply_action(state,{**RECEIVER,'branch_id':'b2'},'sale.create',payload)


def test_old_batch_keeps_portion_and_cost_after_recipe_changes():
    state,batch,recipe=accepted()
    batch['cost']=80
    recipe['yield']=500
    view=visible_state(state,RECEIVER)
    assert next(r for r in view['recipes'] if r['id']==recipe['id'])['availableLots'][0]['available']==4
    execute(state,RECEIVER,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    item=state['sales'][0]['items'][0]
    assert item['batchAllocations'][0]['weight']==.25
    assert item['unitCost']==10


def test_shift_close_freezes_leftovers_until_next_shift_accepts():
    state,batch,recipe=accepted()
    user={**RECEIVER,'register_id':3,'shift_id':7}
    rows=shift_reconciliation.serving_rows(state,user)
    with pytest.raises(custody.CustodyError): shift_reconciliation.close_serving(state,user,[],True)
    with pytest.raises(custody.CustodyError): shift_reconciliation.close_serving(state,user,[{**r,'actualWeight':r['expectedWeight']} for r in rows],False)
    payload=[{**r,'actualWeight':.8,'reason':'Counted shortage'} for r in rows]
    shift_reconciliation.close_serving(state,user,payload,True)
    assert custody.lot_available(batch['servingLots'][0])==0
    with pytest.raises(WorkspaceError): execute(state,user,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    handover=next(d for d in state['logisticsState']['custodyDocuments'] if d['kind']=='handover')
    next_user={**user,'id':999,'shift_id':8,'_receiving_cashier':True}
    execute(state,next_user,'custody.accept',documentId=handover['id'],actualWeight=.8)
    assert batch['servingLots'][0]['responsibleId']==999
    assert batch['servingLots'][0]['acceptedShiftId']==8
    assert custody.lot_available(batch['servingLots'][0])==.8
    assert any(d['kind']=='count' and d['variance']==pytest.approx(-.2) for d in state['logisticsState']['custodyDocuments'])


def test_stale_serving_count_and_pending_writeoff_block_close():
    state,batch,recipe=accepted();user={**RECEIVER,'register_id':3,'shift_id':7}
    rows=shift_reconciliation.serving_rows(state,user)
    execute(state,user,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    with pytest.raises(custody.CustodyError): shift_reconciliation.close_serving(state,user,[{**r,'actualWeight':r['expectedWeight']} for r in rows],True)
    rows=shift_reconciliation.serving_rows(state,user)
    execute(state,user,'custody.writeoff',batchId=batch['id'],lotId=rows[0]['lotId'],weight=.1,reason='Spoiled food')
    with pytest.raises(custody.CustodyError): shift_reconciliation.close_serving(state,user,[{**r,'actualWeight':r['expectedWeight']} for r in rows],True)


def test_ingredient_count_is_mandatory_stale_safe_and_audited():
    state,recipe=scenario()
    before=deepcopy(state)
    with pytest.raises(WorkspaceError): apply_action(state,USER,'production.shift.open',{'counts':[],'requestId':'missing'})
    assert state["logisticsState"]==before["logisticsState"]
    rows=counts(state)
    rows[0]['actualQuantity']+=1
    with pytest.raises(WorkspaceError): apply_action(state,USER,'production.shift.open',{'counts':[],'ingredientCounts':rows,'requestId':'no-reason'})
    assert state["logisticsState"]==before["logisticsState"]
    rows[0]['reason']='Physical inventory'
    payload={'counts':[],'ingredientCounts':rows,'requestId':'count'}
    apply_action(state,USER,'production.shift.open',payload)
    snapshot=deepcopy(state)
    apply_action(state,USER,'production.shift.open',payload)
    assert state==snapshot
    doc=next(d for d in state['logisticsState']['custodyDocuments'] if d['kind']=='ingredient_count')
    assert doc['status']=='review'
    assert state['logisticsState']['branchStocks']['b1'][rows[0]['id']]==rows[0]['actualQuantity']
    with pytest.raises(WorkspaceError): execute(state,USER,'custody.review',documentId=doc['id'],decision='approve',reason='Verified')
    execute(state,MANAGER,'custody.review',documentId=doc['id'],decision='approve',reason='Verified facts')
    assert doc['status']=='approved'
    assert doc['items'][0]['variance']==1


def test_refund_cannot_change_stock_awaiting_handover():
    state,batch,recipe=accepted()
    user={**RECEIVER,'register_id':3,'shift_id':7}
    execute(state,user,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    sale=state['sales'][0]
    rows=shift_reconciliation.serving_rows(state,user)
    shift_reconciliation.close_serving(state,user,[{**r,'actualWeight':r['expectedWeight']} for r in rows],True)
    before=deepcopy(state)
    with pytest.raises(WorkspaceError,match='приёмку'):
        execute(state,MANAGER,'sale.refund',id=sale['id'],reason='Customer refund')
    assert state==before


def test_other_employee_legacy_custody_requires_explicit_handover():
    state,batch,recipe=accepted()
    other={**RECEIVER,'id':999,'register_id':3,'shift_id':7}
    with pytest.raises(custody.CustodyError,match='другого сотрудника'):
        shift_reconciliation.close_serving(state,other,[],True)
    assert batch['servingLots'][0]['responsibleId']==RECEIVER['id']
