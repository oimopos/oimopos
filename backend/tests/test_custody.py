from copy import deepcopy
from uuid import uuid4
import pytest
from app.workspace import apply_action, default_state, visible_state, WorkspaceError
from app import custody

COOK={'id':101,'login':'cook','display_name':'Повар','role':'branch','branch_id':'b1','staff_role':'production','plan_code':'canteen'}
RECEIVER={**COOK,'id':102,'login':'counter','display_name':'Раздача','staff_role':'cashier'}
NEXT={**RECEIVER,'id':103,'display_name':'Вторая смена'}
MANAGER={**COOK,'id':104,'staff_role':'branch_manager','display_name':'Руководитель'}


def execute(state,user,action,**payload):
    payload.setdefault('requestId',str(uuid4()))
    return apply_action(state,user,action,payload)


def setup():
    state=default_state();state['logisticsState']['batches']=[]
    recipe=state['recipes'][0];recipe['yield']=250
    recipe['components']=[{'ingredientId':'rice','gross':300,'net':250}]
    state['logisticsState']['branchStocks']['b1']['rice']=10
    execute(state,COOK,'batch.create',recipeId=recipe['id'],weight=2)
    return state,state['logisticsState']['batches'][0],recipe


def send(state,batch,weight=1,user=COOK,target=RECEIVER):
    acting={**user,'_custody_recipient':{'id':target['id'],'name':target['display_name'],'branchId':'b1'}}
    _,doc=execute(state,acting,'batch.transfer',id=batch['id'],weight=weight,line='Витрина',recipientId=target['id'])
    return doc


def accept(state,doc,weight=1,user=RECEIVER,**extra):
    return execute(state,user,'custody.accept',documentId=doc,actualWeight=weight,**extra)


def test_food_becomes_saleable_only_after_named_recipient_accepts():
    state,batch,recipe=setup();doc=send(state,batch)
    assert custody.kitchen_balance(batch)==1
    assert custody.serving_balance(batch,recipe)==0
    with pytest.raises(WorkspaceError):execute(state,RECEIVER,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    with pytest.raises(WorkspaceError):accept(state,doc,user=NEXT)
    accept(state,doc)
    lot=batch['servingLots'][0]
    assert lot['responsibleId']==RECEIVER['id']
    execute(state,RECEIVER,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    assert lot['soldWeight']==.25
    assert state['sales'][0]['items'][0]['batchAllocations'][0]['responsibleId']==RECEIVER['id']
    assert custody.serving_balance(batch,recipe)==.75


def test_acceptance_discrepancy_records_both_people_without_rewriting_sent_weight():
    state,batch,recipe=setup();doc=send(state,batch)
    accept(state,doc,.8,reason='Фактический вес при приёмке')
    entry=state['logisticsState']['custodyDocuments'][0]
    assert entry['variance']==-.2 and entry['status']=='review'
    assert entry['sender']['id']==COOK['id'] and entry['recipient']['id']==RECEIVER['id']
    assert batch['transfers'][0]['weight']==1 and batch['transfers'][0]['actualWeight']==.8
    assert custody.kitchen_balance(batch)==1 and custody.serving_balance(batch,recipe)==.8
    execute(state,MANAGER,'custody.review',documentId=entry['id'],decision='approve',reason='Проверили весы и тару')
    assert entry['variance']==-.2 and entry['reviewedBy']['id']==MANAGER['id']


@pytest.mark.parametrize('decision,expected',[('approve',.7),('reject',1)])
def test_writeoff_requires_manager_and_reserves_food_immediately(decision,expected):
    state,batch,recipe=setup();accept(state,send(state,batch));lot=batch['servingLots'][0]
    stock=deepcopy(state['logisticsState']['branchStocks'])
    _,doc=execute(state,RECEIVER,'custody.writeoff',batchId=batch['id'],lotId=lot['id'],weight=.3,reason='Испорчено при хранении')
    assert custody.serving_balance(batch,recipe)==.7
    with pytest.raises(WorkspaceError):execute(state,RECEIVER,'custody.review',documentId=doc,decision=decision,reason='Проверено')
    payload={'documentId':doc,'decision':decision,'reason':'Проверено руководителем','requestId':'approval'}
    apply_action(state,MANAGER,'custody.review',payload)
    apply_action(state,MANAGER,'custody.review',payload)
    assert custody.serving_balance(batch,recipe)==expected
    assert state['logisticsState']['branchStocks']==stock
    assert lot['reservedWeight']==0


def test_handover_freezes_sales_and_records_new_custodian_actual_count():
    state,batch,recipe=setup();accept(state,send(state,batch));lot=batch['servingLots'][0]
    actor={**RECEIVER,'_custody_recipient':{'id':NEXT['id'],'name':NEXT['display_name'],'branchId':'b1'}}
    _,doc=execute(state,actor,'custody.handover',batchId=batch['id'],lotId=lot['id'],expectedWeight=1,recipientId=NEXT['id'])
    assert custody.serving_balance(batch,recipe)==0
    accept(state,doc,.9,user=NEXT,reason='Пересчёт при смене')
    assert lot['responsibleId']==NEXT['id'] and custody.serving_balance(batch,recipe)==.9
    with pytest.raises(WorkspaceError):execute(state,RECEIVER,'custody.writeoff',batchId=batch['id'],lotId=lot['id'],weight=.1,reason='Остатки')


def test_count_rejects_stale_balance_and_records_shortage():
    state,batch,recipe=setup();accept(state,send(state,batch));lot=batch['servingLots'][0]
    execute(state,RECEIVER,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    with pytest.raises(WorkspaceError,match='изменился'):execute(state,RECEIVER,'custody.count',batchId=batch['id'],lotId=lot['id'],expectedWeight=1,actualWeight=.7,reason='Пересчёт')
    execute(state,RECEIVER,'custody.count',batchId=batch['id'],lotId=lot['id'],expectedWeight=.75,actualWeight=.7,reason='Остаток по весам')
    assert custody.serving_balance(batch,recipe)==.7
    assert state['logisticsState']['custodyDocuments'][0]['variance']==-.05


def test_cancel_pending_transfer_returns_only_kitchen_reservation():
    state,batch,recipe=setup();doc=send(state,batch)
    execute(state,COOK,'custody.cancel',documentId=doc,reason='Выбрана другая витрина')
    assert custody.kitchen_balance(batch)==2 and custody.serving_balance(batch,recipe)==0
    with pytest.raises(WorkspaceError):accept(state,doc)


def test_kitchen_writeoff_and_branch_isolation():
    state,batch,recipe=setup()
    with pytest.raises(WorkspaceError):execute(state,{**MANAGER,'branch_id':'b2'},'custody.writeoff',batchId=batch['id'],weight=.1,reason='Порча')
    _,doc=execute(state,COOK,'custody.writeoff',batchId=batch['id'],weight=.5,reason='Переготовленное блюдо')
    assert custody.kitchen_balance(batch)==1.5
    execute(state,MANAGER,'custody.review',documentId=doc,decision='approve',reason='Подтверждена порча')
    assert custody.kitchen_balance(batch)==1.5
    assert not visible_state(state,{**MANAGER,'branch_id':'b2'})['logisticsState']['custodyDocuments']


def test_legacy_data_does_not_invent_recipient():
    state,batch,recipe=setup()
    del batch['servingLots'];batch['transferredWeight']=1;batch['soldPortions']=1
    custody.initialize(batch,recipe)
    assert batch['servingLots'][0]['responsibleId'] is None
    assert custody.serving_balance(batch,recipe)==0
    assert custody.lot_balance(batch["servingLots"][0])==.75


def test_sale_requires_explicit_lot_when_multiple_custodians_have_same_dish():
    state,batch,recipe=setup()
    accept(state,send(state,batch,1,target=RECEIVER),1,user=RECEIVER)
    accept(state,send(state,batch,1,target=NEXT),1,user=NEXT)
    first,second=batch['servingLots']
    with pytest.raises(WorkspaceError,match='Выберите витрину'):
        execute(state,RECEIVER,'sale.create',items=[{'id':recipe['id'],'quantity':1}],paymentMethod='card')
    execute(state,RECEIVER,'sale.create',items=[{'id':recipe['id'],'lotId':first['id'],'quantity':1},{'id':recipe['id'],'lotId':second['id'],'quantity':2}],paymentMethod='card')
    assert first['soldWeight']==.25 and second['soldWeight']==.5
    assert [row['batchAllocations'][0]['responsibleId'] for row in state['sales'][0]['items']]==[RECEIVER['id'],NEXT['id']]
    assert len([d for d in custody.context(state,'b1',MANAGER)['documents'] if d['kind']=='sale'])==2


def test_duplicate_implicit_and_explicit_lot_cannot_oversell():
    state,batch,recipe=setup();accept(state,send(state,batch));lot=batch['servingLots'][0]
    with pytest.raises(WorkspaceError):
        execute(state,RECEIVER,'sale.create',items=[{'id':recipe['id'],'quantity':3},{'id':recipe['id'],'lotId':lot['id'],'quantity':3}],paymentMethod='card')
    assert lot['soldWeight']==0
    with pytest.raises(WorkspaceError):
        execute(state,RECEIVER,'sale.create',items=[{'id':recipe['id'],'lotId':'foreign-lot','quantity':1}],paymentMethod='card')


def test_close_requires_zero_balances_and_manager_decisions():
    state,batch,recipe=setup()
    _,doc=execute(state,COOK,'custody.writeoff',batchId=batch['id'],weight=2,reason='Порча всего выпуска')
    with pytest.raises(WorkspaceError):execute(state,MANAGER,'custody.close',batchId=batch['id'],reason='Закрытие')
    execute(state,MANAGER,'custody.review',documentId=doc,decision='approve',reason='Порча подтверждена')
    execute(state,MANAGER,'custody.close',batchId=batch['id'],reason='Остаток нулевой, документы проверены')
    assert batch['status']=='closed'


def test_cross_branch_recipient_is_rejected_even_for_company_admin():
    state,batch,recipe=setup()
    user={**MANAGER,'role':'owner','_custody_recipient':{'id':RECEIVER['id'],'name':'Раздача','branchId':'b2'}}
    with pytest.raises(WorkspaceError):execute(state,user,'batch.transfer',id=batch['id'],weight=1,line='Витрина',recipientId=RECEIVER['id'])


def test_old_stock_requires_real_cashier_acceptance_before_sale():
    state, batch, recipe = setup()
    del batch['servingLots']
    batch.update(transferredWeight=1, soldPortions=0, status='serving')
    cashier = {**MANAGER, 'id': 88, 'staff_role': 'cashier', 'shift_id': 7}
    raw_stock = deepcopy(state['logisticsState']['branchStocks'])
    assert visible_state(state, cashier)['recipes'][0]['availableLots'] == []
    with pytest.raises(WorkspaceError):
        apply_action(state, cashier, 'sale.create', {'items':[{'id':recipe['id'],'quantity':1,'lotId':'legacy-'+batch['id']}], 'paymentMethod':'card'})
    payload = {'documentId':'legacy:'+batch['id'], 'actualWeight':.75, 'reason':'Пересчёт при приёмке', 'requestId':'opening-stock'}
    with pytest.raises(WorkspaceError):
        apply_action(state, {**cashier,'shift_id':None}, 'pos.receiving.accept', payload)
    with pytest.raises(WorkspaceError):
        apply_action(state, {**cashier,'branch_id':'another'}, 'pos.receiving.accept', payload)
    apply_action(state, cashier, 'pos.receiving.accept', payload)
    apply_action(state, cashier, 'pos.receiving.accept', payload)
    assert custody.serving_balance(batch,recipe)==.75
    assert batch['servingLots'][0]['responsibleId']==88
    assert len([d for d in state['logisticsState']['custodyDocuments'] if d['kind']=='opening_acceptance'])==1
    assert state['logisticsState']['branchStocks']==raw_stock
    apply_action(state, cashier, 'sale.create', {'items':[{'id':recipe['id'],'quantity':1}], 'paymentMethod':'card'})
    assert custody.serving_balance(batch,recipe)==.5


def test_terminal_writeoff_reserves_food_and_needs_manager_review():
    state,batch,recipe=setup();accept(state,send(state,batch));lot=batch['servingLots'][0]
    cashier={**RECEIVER,'id':999,'display_name':'Дежурный кассир','shift_id':7}
    payload={'batchId':batch['id'],'lotId':lot['id'],'weight':.5,'reason':'Истёк срок хранения','requestId':'terminal-writeoff'}
    stock=deepcopy(state['logisticsState']['branchStocks'])
    _,document_id=apply_action(state,cashier,'pos.serving.writeoff',payload)
    apply_action(state,cashier,'pos.serving.writeoff',payload)
    assert custody.serving_balance(batch,recipe)==.5
    doc=next(d for d in state['logisticsState']['custodyDocuments'] if d['id']==document_id)
    assert doc['actor']['id']==999 and doc['responsible']['id']==RECEIVER['id']
    with pytest.raises(WorkspaceError):execute(state,cashier,'custody.review',documentId=document_id,decision='approve',reason='Подтверждаю')
    execute(state,MANAGER,'custody.review',documentId=document_id,decision='reject',reason='Блюдо пригодно')
    assert custody.serving_balance(batch,recipe)==1
    _,document_id=apply_action(state,cashier,'pos.serving.writeoff',{**payload,'requestId':'again'})
    execute(state,MANAGER,'custody.review',documentId=document_id,decision='approve',reason='Подтверждена порча')
    assert custody.serving_balance(batch,recipe)==.5 and lot['writeoffWeight']==.5
    assert state['logisticsState']['branchStocks']==stock
    for denied in [{**cashier,'shift_id':None},{**cashier,'branch_id':'b2'},{**cashier,'plan_code':'restaurant'}]:
        with pytest.raises(WorkspaceError):apply_action(state,denied,'pos.serving.writeoff',{**payload,'requestId':'forbidden'})
