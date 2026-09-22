from copy import deepcopy
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app import main
from app.workspace import apply_action, default_state, production_context, WorkspaceError

USER={'id':2,'login':'cook','display_name':'Повар','role':'branch','branch_id':'b1','staff_role':'production','plan_code':'canteen','register_id':3,'shift_id':4,'access_permissions':{'posAccess':True,'production':True},'_custody_recipient':{'id':2,'name':'Повар','branchId':'b1'}}


def scenario():
    state=default_state()
    state['logisticsState']['batches']=[]
    recipe=state['recipes'][0]
    recipe['yield']=250
    recipe['components']=[{'ingredientId':'rice','gross':200,'net':150},{'ingredientId':'rice','gross':100,'net':100}]
    state['logisticsState']['branchStocks']['b1']['rice']=3
    return state,recipe


def test_release_from_terminal_consumes_gross_once_and_makes_portions_available():
    state,recipe=scenario()
    payload={'recipeId':recipe['id'],'weight':.5,'line':'Витрина 1','requestId':'release-1'}
    kind,key=apply_action(state,USER,'batch.release',payload)
    batch=state['logisticsState']['batches'][0]
    assert kind=='production_batch' and key==batch['id']
    assert batch['status']=='kitchen' and batch['transferredWeight']==0
    doc=state['logisticsState']['custodyDocuments'][0]
    apply_action(state,USER,'custody.accept',{'documentId':doc['id'],'actualWeight':.5,'requestId':'accept-release'})
    assert batch['createdBy']==batch['transfers'][0]['transferredBy']=='Повар'
    assert state['logisticsState']['branchStocks']['b1']['rice']==pytest.approx(2.4)
    apply_action(state,USER,'batch.release',payload)
    assert len(state['logisticsState']['batches'])==1
    assert state['logisticsState']['branchStocks']['b1']['rice']==pytest.approx(2.4)
    apply_action(state,USER,'sale.create',{'items':[{'id':recipe['id'],'quantity':2}],'paymentMethod':'card'})
    assert state['logisticsState']['branchStocks']['b1']['rice']==pytest.approx(2.4)


def test_release_is_atomic_on_insufficient_stock_or_invalid_destination():
    for payload,match in [({'weight':5,'line':'Витрина'},'недостаточно'),({'weight':.5,'line':'x'*81},'Укажите витрину')]:
        state,recipe=scenario()
        before=deepcopy(state['logisticsState'])
        with pytest.raises(WorkspaceError,match=match):
            apply_action(state,USER,'batch.release',{'recipeId':recipe['id'],'requestId':'release-1',**payload})
        assert state['logisticsState']['branchStocks']==before['branchStocks']
        assert state['logisticsState']['batches']==before['batches']
        assert state['logisticsState'].get('stockLedger',[])==before.get('stockLedger',[])


def test_transfer_existing_batch_without_consuming_again_and_replay_safe():
    state,recipe=scenario()
    _,key=apply_action(state,USER,'batch.create',{'recipeId':recipe['id'],'weight':1})
    stock=deepcopy(state['logisticsState']['branchStocks'])
    payload={'id':key,'weight':.4,'line':'Витрина 2','requestId':'transfer-1'}
    apply_action(state,USER,'batch.transfer',payload)
    apply_action(state,USER,'batch.transfer',payload)
    batch=state['logisticsState']['batches'][0]
    assert batch['transferredWeight']==0
    doc=state['logisticsState']['custodyDocuments'][0]
    apply_action(state,USER,'custody.accept',{'documentId':doc['id'],'actualWeight':.4,'requestId':'accept-transfer'})
    assert batch['transferredWeight']==.4 and batch['status']=='partial'
    assert len(batch['transfers'])==1
    assert state['logisticsState']['branchStocks']==stock
    with pytest.raises(WorkspaceError): apply_action(state,{**USER,'branch_id':'b2'},'batch.transfer',payload)
    with pytest.raises(WorkspaceError): apply_action(state,USER,'batch.transfer',{**payload,'weight':.7,'requestId':'transfer-2'})
    assert batch['transferredWeight']==.4
    ctx=production_context(state,'b1')
    assert ctx['batches'][0]['availableWeight']==.6
    assert not production_context(state,'b2')['batches']


def test_production_context_hides_cost_and_aggregates_shared_components():
    state,recipe=scenario()
    ctx=production_context(state,'b1')
    row=next(row for row in ctx['recipes'] if row['id']==recipe['id'])
    assert row['maxWeight']==2.5
    assert set(row)=={'id','name','yield','maxWeight'}


def test_production_permission_and_plan_enforced(monkeypatch):
    main._authorize_staff_action(USER,'batch.release')
    denied={**USER,'staff_role':'cashier','access_permissions':{'posAccess':True}}
    with pytest.raises(HTTPException): main._authorize_staff_action(denied,'batch.release')
    monkeypatch.setattr(main,'_current_pos_operator',lambda *args:denied)
    with pytest.raises(HTTPException) as error: main.pos_production_context(None,USER,None)
    assert error.value.status_code==403
    monkeypatch.setattr(main,'_current_pos_operator',lambda *args:USER)
    with pytest.raises(HTTPException) as error: main.pos_production_context(None,{**USER,'plan_code':'restaurant'},None)
    assert error.value.status_code==403
    state,recipe=scenario()
    with pytest.raises(WorkspaceError): apply_action(state,{**USER,'plan_code':'restaurant'},'batch.release',{'recipeId':recipe['id'],'weight':1,'requestId':'r','line':'Витрина'})


def test_terminal_action_uses_authenticated_cook_without_cash_shift(monkeypatch):
    from contextlib import nullcontext
    from starlette.requests import Request
    from app.schemas import WorkspaceActionInput
    request=Request({'type':'http','method':'POST','headers':[(b'x-ashkana-client',b'pos')]})
    terminal={**USER,'id':9,'staff_role':'pos_terminal','access_permissions':{},'tenant_id':'t1'}
    monkeypatch.setattr(main,'_check_origin',lambda request:None)
    monkeypatch.setattr(main,'_current_pos_operator',lambda *args:USER)
    monkeypatch.setattr(main,'_current_pos_shift',lambda *args:None)
    monkeypatch.setattr(main,'_production_recipients',lambda *args:[USER['_custody_recipient']])
    command=WorkspaceActionInput(action='batch.release',payload={'recipeId':201,'weight':.5,'line':'Витрина','recipientId':2,'requestId':'r1'})
    state,recipe=scenario()
    apply_action(state, USER, 'production.shift.open', {'counts': [], 'ingredientCounts':[{'id':r['id'],'expectedQuantity':r['quantity'],'actualQuantity':r['quantity']} for r in __import__('app.production_shifts',fromlist=['ingredient_stocks']).ingredient_stocks(state,'b1')], 'requestId': 'shift-open'})
    monkeypatch.setattr(main,'_workspace_row',lambda *args,**kwargs:{'payload':state,'version':1})
    class Connection:
        def transaction(self): return nullcontext()
        def execute(self,*args): return SimpleNamespace()
    response=main.workspace_action(command,request,terminal,'cookie',Connection())
    assert response['entity']['type']=='production_batch'
    assert state['logisticsState']['batches'][0]['createdBy']=='Повар'
    assert response['state']['products']
    assert 'components' not in response['state']['recipes'][0]


def test_unified_serving_uses_ready_food_then_only_missing_raw_ingredients():
    state, recipe = scenario()
    apply_action(state, USER, 'batch.create', {'recipeId': recipe['id'], 'weight': .5})
    before = state['logisticsState']['branchStocks']['b1']['rice']
    payload = {'recipeId': recipe['id'], 'weight': .75, 'line': 'Раздача', 'recipientId': 2, 'requestId': 'unified'}
    apply_action(state, USER, 'batch.serve', payload)
    assert state['logisticsState']['branchStocks']['b1']['rice'] == pytest.approx(before - .3)
    assert len(state['logisticsState']['custodyDocuments']) == 2
    snapshot = deepcopy(state)
    apply_action(state, USER, 'batch.serve', payload)
    assert state == snapshot


def test_unified_serving_rolls_back_ready_transfer_if_raw_stock_insufficient():
    state, recipe = scenario()
    apply_action(state, USER, 'batch.create', {'recipeId': recipe['id'], 'weight': .5})
    state['logisticsState']['branchStocks']['b1']['rice'] = 0
    snapshot = deepcopy(state)
    with pytest.raises(WorkspaceError, match='недостаточно'):
        apply_action(state, USER, 'batch.serve', {'recipeId': recipe['id'], 'weight': 1, 'line': 'Раздача', 'recipientId': 2, 'requestId': 'short'})
    assert state == snapshot
    apply_action(state, USER, 'batch.serve', {'recipeId': recipe['id'], 'weight': .5, 'line': 'Раздача', 'recipientId': 2, 'requestId': 'ready'})
    assert state['logisticsState']['branchStocks']['b1']['rice'] == 0


def test_cashier_queue_accepts_any_current_cashier_once_and_enables_sale():
    state, recipe = scenario()
    apply_action(state, USER, 'batch.serve', {'recipeId': recipe['id'], 'weight': .5, 'requestId': 'queue'})
    doc = state['logisticsState']['custodyDocuments'][0]
    assert doc['recipient']['kind'] == 'branch_cashiers' and doc['line'] == 'Раздача'
    cashier = {**USER, 'id': 77, 'display_name': 'Кассир на смене', 'staff_role': 'cashier', 'access_permissions': {'posAccess': True}}
    with pytest.raises(WorkspaceError):
        apply_action(state, cashier, 'sale.create', {'items': [{'id': recipe['id'], 'quantity': 1}], 'paymentMethod': 'card'})
    payload = {'documentId': doc['id'], 'actualWeight': .5, 'requestId': 'receipt'}
    apply_action(state, cashier, 'pos.receiving.accept', payload)
    apply_action(state, cashier, 'pos.receiving.accept', payload)
    batch = state['logisticsState']['batches'][0]
    assert len(batch['servingLots']) == 1 and batch['servingLots'][0]['responsibleId'] == 77
    with pytest.raises(WorkspaceError, match='обработана'):
        apply_action(state, {**cashier, 'id': 78}, 'pos.receiving.accept', {**payload, 'requestId': 'second'})
    apply_action(state, cashier, 'sale.create', {'items': [{'id': recipe['id'], 'quantity': 1}], 'paymentMethod': 'card'})


def test_cashier_rejection_returns_cooked_food_without_restoring_raw_ingredients():
    from app import custody
    state, recipe = scenario()
    apply_action(state, USER, 'batch.serve', {'recipeId': recipe['id'], 'weight': .5, 'requestId': 'queue'})
    doc = state['logisticsState']['custodyDocuments'][0]
    stock = deepcopy(state['logisticsState']['branchStocks'])
    cashier = {**USER, 'id': 77, 'staff_role': 'cashier'}
    payload = {'documentId': doc['id'], 'reason': 'Блюдо не доставлено', 'requestId': 'reject'}
    for denied in [USER, {**cashier, 'shift_id': None}, {**cashier, 'branch_id': 'other'}]:
        with pytest.raises(WorkspaceError):
            apply_action(state, denied, 'pos.receiving.reject', payload)
    apply_action(state, cashier, 'pos.receiving.reject', payload)
    assert doc['status'] == 'rejected'
    assert custody.kitchen_balance(state['logisticsState']['batches'][0]) == .5
    assert state['logisticsState']['branchStocks'] == stock


def test_multi_dish_transfer_is_atomic_for_shared_ingredient_and_retries():
    state, recipe = scenario()
    second = deepcopy(recipe)
    second.update(id='second-recipe', name='Второе блюдо')
    state['recipes'].append(second)
    state['logisticsState']['branchStocks']['b1']['rice'] = 1
    items = [{'recipeId': recipe['id'], 'weight': .5}, {'recipeId': second['id'], 'weight': .5}]
    before = deepcopy(state)
    with pytest.raises(WorkspaceError, match='Второе блюдо.*недостаточно'):
        apply_action(state, USER, 'batch.serve_many', {'items': items, 'requestId': 'multi'})
    assert state['logisticsState'] == before['logisticsState']
    state['logisticsState']['branchStocks']['b1']['rice'] = 3
    result = apply_action(state, USER, 'batch.serve_many', {'items': items, 'requestId': 'multi'})
    assert result[0] == 'serving_document'
    assert state['logisticsState']['branchStocks']['b1']['rice'] == pytest.approx(1.8)
    docs = state['logisticsState']['custodyDocuments']
    assert len(docs) == 2 and all(d['servingDocumentId'] == result[1] for d in docs)
    after = deepcopy(state)
    assert apply_action(state, USER, 'batch.serve_many', {'items': items, 'requestId': 'multi'}) == result
    assert state == after
    with pytest.raises(WorkspaceError):
        apply_action(state, USER, 'batch.serve_many', {'items': items[:1], 'requestId': 'multi'})


@pytest.mark.parametrize('items', [[], [None], [{'recipeId': 'missing', 'weight': 1}]])
def test_multi_transfer_validates_rows(items):
    state, _ = scenario()
    with pytest.raises(WorkspaceError):
        apply_action(state, USER, 'batch.serve_many', {'items': items, 'requestId': 'bad'})


def test_restaurant_cannot_use_canteen_receiving_endpoint():
    with pytest.raises(HTTPException) as error:
        main.pos_receiving(None, {**USER, 'plan_code':'restaurant'}, None)
    assert error.value.status_code == 403
