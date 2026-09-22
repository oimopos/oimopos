from copy import deepcopy
import pytest
from app.workspace import apply_action, WorkspaceError
from app import production_shifts
from test_terminal_production import USER, scenario


def ingredient_counts(state):
    return [{'id':row['id'],'expectedQuantity':row['quantity'],'actualQuantity':row['quantity']} for row in production_shifts.ingredient_stocks(state,'b1')]


def test_shift_open_close_and_next_employee_takes_kitchen_responsibility():
    state, recipe = scenario()
    apply_action(state, USER, 'batch.create', {'recipeId': recipe['id'], 'weight': 1})
    counts = [{**row, 'actualWeight': row['expectedWeight']} for row in production_shifts.context(state, 'b1')['counts']]
    payload = {'ingredientCounts':ingredient_counts(state), 'counts': counts, 'requestId': 'open'}
    apply_action(state, USER, 'production.shift.open', payload)
    apply_action(state, USER, 'production.shift.open', payload)
    assert len(state['logisticsState']['productionShifts']) == 1
    other = {**USER, 'id': 99, 'display_name': 'Следующий повар'}
    with pytest.raises(WorkspaceError):
        apply_action(state, other, 'production.shift.open', {**payload, 'requestId': 'duplicate'})
    with pytest.raises(WorkspaceError):
        apply_action(state, other, 'production.shift.close', {**payload, 'requestId': 'not-mine'})
    apply_action(state, USER, 'production.shift.close', {**payload, 'requestId': 'close'})
    assert production_shifts.current(state, 'b1') is None
    apply_action(state, other, 'production.shift.open', {**payload, 'requestId': 'next'})
    batch = state['logisticsState']['batches'][0]
    assert batch['createdById'] == USER['id'] and batch['kitchenResponsibleId'] == 99
    apply_action(state, other, 'batch.serve', {'recipeId': recipe['id'], 'weight': .5, 'requestId': 'send'})
    with pytest.raises(WorkspaceError, match='приёмку'):
        apply_action(state, other, 'production.shift.close', {'counts': [], 'requestId': 'pending'})


def test_counts_are_atomic_and_stale_counts_rejected():
    state, recipe = scenario()
    apply_action(state, USER, 'batch.create', {'recipeId': recipe['id'], 'weight': 1})
    row = production_shifts.context(state, 'b1')['counts'][0]
    before = deepcopy(state)
    for counts in [[], [{**row, 'expectedWeight': 2, 'actualWeight': 1}], [{**row, 'actualWeight': .8}]]:
        with pytest.raises(WorkspaceError):
            apply_action(state, USER, 'production.shift.open', {'counts': counts, 'requestId': 'invalid'})
        assert state == before
    apply_action(state, USER, 'production.shift.open', {'ingredientCounts':ingredient_counts(state), 'counts': [{**row, 'actualWeight': .8, 'reason': 'Фактический пересчёт'}], 'requestId': 'valid'})
    assert production_shifts.context(state, 'b1')['counts'][0]['expectedWeight'] == .8
    assert state['logisticsState']['custodyDocuments'][0]['status'] == 'review'


def test_cashier_cannot_open_production_shift():
    state, _ = scenario()
    with pytest.raises(WorkspaceError):
        apply_action(state, {**USER, 'staff_role': 'cashier'}, 'production.shift.open', {'counts': [], 'requestId': 'denied'})


def test_ingredient_stocks_are_branch_scoped_and_saved_on_shift_close():
    state, _ = scenario()
    ingredient = state['ingredients'][0]
    key = str(ingredient['id'])
    state['logisticsState']['branchStocks']['b1'][key] = 12.5
    state['logisticsState']['branchStocks']['b2'] = {key: 999}
    rows = production_shifts.context(state, 'b1')['ingredientStocks']
    assert next(row for row in rows if row['id'] == key)['quantity'] == 12.5
    assert all(set(row) == {'id', 'name', 'unit', 'quantity'} for row in rows)
    apply_action(state, USER, 'production.shift.open', {'ingredientCounts':ingredient_counts(state), 'counts': [], 'requestId': 'stock-open'})
    state['logisticsState']['branchStocks']['b1'][key] = 7.25
    apply_action(state, USER, 'production.shift.close', {'ingredientCounts':ingredient_counts(state), 'counts': [], 'requestId': 'stock-close'})
    shift = state['logisticsState']['productionShifts'][0]
    assert next(row for row in shift['openingIngredientStocks'] if row['id'] == key)['quantity'] == 12.5
    assert next(row for row in shift['closingIngredientStocks'] if row['id'] == key)['quantity'] == 7.25
    state['logisticsState']['branchStocks']['b1'][key] = 1
    assert next(row for row in shift['closingIngredientStocks'] if row['id'] == key)['quantity'] == 7.25
