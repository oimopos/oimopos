from copy import deepcopy
import pytest
from app.workspace import apply_action, default_state, visible_state, WorkspaceError

OWNER={'id':1,'role':'owner','display_name':'Owner'}
IMAGE='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='
COLOR='#123abc'

@pytest.mark.parametrize('kind,collection',[('recipe','recipes'),('ingredient','ingredients'),('preparation','preparations')])
def test_appearance_persists_independently_of_stock_and_can_be_cleared(kind,collection):
    state=default_state()
    if kind=='preparation':
        item={'id':'pf-cover','name':'Тесто','station':'Кухня','yield':100,'components':[{'ingredientId':'rice','gross':100,'net':100}]}
    else:
        item=deepcopy(state[collection][0])
        if kind=='recipe': item['station']='Кухня'
    before=deepcopy(state['logisticsState'])
    apply_action(state,OWNER,kind+'.upsert',{**item,'image':IMAGE,'color':COLOR})
    result=next(row for row in state[collection] if str(row['id'])==str(item['id']))
    assert (result['image'],result['color'])==(IMAGE,COLOR)
    apply_action(state,OWNER,kind+'.upsert',item)
    assert result['image']==IMAGE
    apply_action(state,OWNER,kind+'.upsert',{**item,'image':'','color':COLOR})
    assert result['image']=='' and result['color']==COLOR
    if kind!='preparation': assert state['logisticsState']==before
    with pytest.raises(WorkspaceError): apply_action(state,OWNER,kind+'.upsert',{**item,'image':'javascript:alert(1)'})


def test_category_rename_keeps_photo_and_does_not_recolor_recipes():
    state=default_state(); colors={r['id']:r['color'] for r in state['recipes']}
    apply_action(state,OWNER,'category.upsert',{'kind':'menu','originalName':'Горячее','name':'Горячее','color':COLOR,'image':IMAGE})
    apply_action(state,OWNER,'category.upsert',{'kind':'menu','originalName':'Горячее','name':'Обед'})
    assert next(c for c in state['menuCategories'] if c['name']=='Обед')['image']==IMAGE
    assert {r['id']:r['color'] for r in state['recipes']}==colors
    apply_action(state,OWNER,'category.upsert',{'kind':'ingredient','originalName':'Крупы','name':'Крупы','color':COLOR,'image':IMAGE})
    apply_action(state,OWNER,'category.upsert',{'kind':'ingredient','originalName':'Крупы','name':'Зерно'})
    assert state['ingredientCategoryCovers']['Зерно']=={'image':IMAGE,'color':COLOR}
    assert 'Крупы' not in state['ingredientCategoryCovers']


def test_cashier_receives_recipe_photo_and_variant_specific_appearance():
    state=default_state(); recipe=deepcopy(state['recipes'][0]);recipe['station']='Кухня'
    apply_action(state,OWNER,'recipe.upsert',{**recipe,'image':IMAGE,'color':COLOR})
    apply_action(state,OWNER,'product.group.upsert',{'id':'cover-variants','name':'Сок','category':'Напитки','image':IMAGE,'color':COLOR,'variants':[{'name':'Яблоко','price':100},{'name':'Вишня','price':120,'color':'#ff2244','image':''}]})
    cashier={'id':2,'role':'branch','branch_id':'b1','staff_role':'cashier','display_name':'Кассир'}
    result=visible_state(state,cashier)
    assert result['recipes'][0]['image']==IMAGE
    variants=[p for p in result['products'] if p.get('groupName')=='Сок']
    assert variants[0]['image']==IMAGE and variants[1]['image']=='' and variants[1]['color']=='#ff2244'
