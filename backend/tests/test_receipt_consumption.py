from copy import deepcopy
import pytest
from app.workspace import apply_action
from test_service_plans import scenario, USER
from test_custody import setup, send, accept, execute, RECEIVER


def test_restaurant_receipt_keeps_ingredient_snapshot_after_catalog_change():
    state, recipe = scenario()
    ingredient = {'id':'i1', 'name':'Original ingredient', 'unit':'kg'}
    state['ingredients'].append(ingredient)
    ingredient['name'] = 'Original ingredient'
    apply_action(state, USER, 'sale.create', {'items':[{'id':recipe['id'],'quantity':2}], 'paymentMethod':'card'})
    allocation = state['sales'][0]['items'][0]['ingredientAllocations'][0]
    snapshot = deepcopy(allocation)
    ingredient['name'] = 'Renamed'
    ingredient['unit'] = 'changed'
    recipe['components'] = []
    assert allocation == snapshot
    assert allocation['name'] == 'Original ingredient'
    assert allocation['quantity'] == pytest.approx(.6)


def test_canteen_receipt_uses_production_snapshot_without_consuming_again():
    state, batch, recipe = setup()
    snapshot = deepcopy(batch['ingredientSnapshot'])
    assert snapshot[0]['quantity'] == pytest.approx(2.4)
    accept(state, send(state, batch))
    stocks = deepcopy(state['logisticsState']['branchStocks'])
    execute(state, RECEIVER, 'sale.create', items=[{'id':recipe['id'],'quantity':1}], paymentMethod='card')
    allocation = state['sales'][0]['items'][0]['batchAllocations'][0]
    assert allocation['batchNumber'] == batch['number']
    assert allocation['productionIngredients'][0]['quantity'] == pytest.approx(.3)
    batch['ingredientSnapshot'][0]['name'] = 'Changed'
    assert allocation['productionIngredients'][0]['name'] == snapshot[0]['name']
    assert state['logisticsState']['branchStocks'] == stocks
