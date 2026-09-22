"""Immutable physical counts and pooled handover at cash shift close."""
from uuid import uuid4
from . import custody


def serving_rows(state, user):
    rows = []
    recipes = {str(r['id']): r for r in state.get('recipes', [])}
    for batch in state['logisticsState'].get('batches', []):
        if batch.get('branchId') != user.get('branch_id') or batch.get('status') == 'closed':
            continue
        recipe = recipes.get(str(batch['recipeId']), {})
        custody.initialize(batch, recipe)
        for lot in batch['servingLots']:
            if lot.get('handoverId') or lot.get('legacy') or not lot.get('acceptedAt'):
                continue
            owned = str(lot.get('registerId')) == str(user.get('register_id')) if lot.get('registerId') is not None else str(lot.get('responsibleId')) == str(user.get('id'))
            if owned:
                rows.append({'batchId': batch['id'], 'lotId': lot['id'], 'name': recipe.get('name', 'Блюдо'), 'number': batch['number'], 'expectedWeight': custody.lot_balance(lot)})
    return rows


def close_serving(state, user, counts, confirmed):
    custody.require(confirmed, 'Подтвердите пересчёт остатков раздачи', 422)
    for batch in state['logisticsState'].get('batches', []):
        if batch.get('branchId') != user.get('branch_id') or batch.get('status') == 'closed':
            continue
        for lot in batch.get('servingLots', []):
            if lot.get('registerId') is None and lot.get('acceptedAt') and not lot.get('handoverId') and custody.lot_balance(lot) > 0:
                custody.require(str(lot.get('responsibleId')) == str(user.get('id')), 'Есть старые остатки другого сотрудника без привязки к кассе. Руководитель должен оформить передачу ответственности')
    expected = serving_rows(state, user)
    custody.require(isinstance(counts, list) and all(isinstance(r, dict) for r in counts) and len(counts) == len(expected) and {r.get('lotId') for r in counts} == {r['lotId'] for r in expected}, 'Остатки изменились. Обновите окно закрытия смены')
    lots = {r['lotId'] for r in expected}
    pending = [d for d in state['logisticsState'].get('custodyDocuments', []) if d.get('branchId') == user['branch_id'] and d.get('status') == 'pending' and (d.get('kind') == 'transfer' or d.get('lotId') in lots)]
    custody.require(not pending, 'Завершите приёмку и рассмотрение заявок на списание и излишки')
    for row in expected:
        supplied = next(r for r in counts if r.get('lotId') == row['lotId'])
        custody.require('actualWeight' in supplied and 'expectedWeight' in supplied, 'Укажите фактические остатки', 422)
        custody.require(abs(custody.number(supplied['expectedWeight'])-row['expectedWeight']) <= 1e-6, 'Остатки изменились. Повторите пересчёт')
        if abs(custody.number(supplied['actualWeight'])-row['expectedWeight']) > 1e-6:
            custody.reason(supplied)
    facts = []
    for row in expected:
        supplied = next(r for r in counts if r['lotId'] == row['lotId'])
        batch = next(b for b in state['logisticsState']['batches'] if b['id'] == row['batchId'])
        lot = next(l for l in batch['servingLots'] if l['id'] == row['lotId'])
        _, doc_id = custody.apply(state, {**user, '_cash_shift_count': True}, 'custody.count', {**supplied, 'batchId':row['batchId'], 'requestId':str(uuid4())})
        fact = {**row, 'actualWeight':custody.number(supplied['actualWeight']), 'reason':supplied.get('reason',''), 'documentId':doc_id}
        if fact['actualWeight'] > 0:
            entry = custody.document(state, user, batch, 'handover', {'requestId':str(uuid4())}, lotId=lot['id'], weight=fact['actualWeight'], line=lot.get('line','Раздача'), status='pending', previousResponsible={'id':lot.get('responsibleId'), 'name':lot.get('responsibleName')}, recipient={'kind':'branch_cashiers','branchId':user['branch_id'],'name':'Кассир следующей смены'}, shiftId=user.get('shift_id'))
            lot['handoverId'] = entry['id']
            fact['handoverId'] = entry['id']
        facts.append(fact)
    state['logisticsState'].setdefault('cashShiftCounts', []).append({'id':'cash-count-'+str(uuid4()), 'shiftId':user.get('shift_id'), 'branchId':user['branch_id'], 'registerId':user.get('register_id'), 'createdAt':custody.now(), 'actor':custody.snapshot_actor(user), 'counts':facts})
    return facts


def count_ingredients(state, user, supplied, phase, shift_id):
    from .production_shifts import ingredient_stocks
    expected = ingredient_stocks(state, user['branch_id'])
    custody.require(isinstance(supplied, list) and all(isinstance(r, dict) for r in supplied) and len(supplied) == len(expected) and {str(r.get('id')) for r in supplied} == {r['id'] for r in expected}, 'Пересчитайте все ингредиенты кухни', 422)
    facts = []
    for row in expected:
        actual = next(r for r in supplied if str(r.get('id')) == row['id'])
        custody.require('expectedQuantity' in actual and 'actualQuantity' in actual, 'Укажите фактический остаток ингредиента', 422)
        custody.require(abs(custody.number(actual['expectedQuantity'])-row['quantity']) <= 1e-6, 'Остатки ингредиентов изменились. Повторите пересчёт')
        quantity = custody.number(actual['actualQuantity'])
        variance = round(quantity-row['quantity'], 6)
        note = custody.reason(actual) if abs(variance) > 1e-6 else str(actual.get('reason',''))
        facts.append({**row, 'expectedQuantity':row['quantity'], 'actualQuantity':quantity, 'variance':variance, 'reason':note})
    docs = state['logisticsState'].setdefault('custodyDocuments', [])
    changes = [r for r in facts if abs(r['variance']) > 1e-6]
    doc = {'id':'ingredient-count-'+str(uuid4()), 'number':f'ИНГ-{len(docs)+1:06}', 'kind':'ingredient_count', 'branchId':user['branch_id'], 'batchId':None, 'batchNumber':'Кухня', 'name':'Пересчёт ингредиентов', 'createdAt':custody.now(), 'actor':custody.snapshot_actor(user), 'shiftId':shift_id, 'phase':phase, 'items':facts, 'status':'review' if changes else 'recorded', 'reason':'\n'.join(f"{r['name']}: {r['expectedQuantity']} → {r['actualQuantity']} {r['unit']}. {r['reason']}" for r in changes)}
    docs.insert(0, doc)
    for row in changes:
        stock = state['logisticsState']['branchStocks'].setdefault(user['branch_id'], {})
        stock[row['id']] = row['actualQuantity']
        state['logisticsState'].setdefault('stockLedger', []).insert(0, {'id':'ledger-'+str(uuid4()), 'branchId':user['branch_id'], 'itemId':row['id'], 'quantity':row['variance'], 'unitCost':state['logisticsState'].get('branchCosts',{}).get(user['branch_id'],{}).get(row['id'],0), 'movementType':'ingredient_count', 'documentNumber':doc['number'], 'createdAt':doc['createdAt'], 'createdBy':user['display_name']})
    return facts
