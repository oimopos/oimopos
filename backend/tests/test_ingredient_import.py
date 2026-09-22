from copy import deepcopy
import pytest
from app.workspace import apply_action, default_state, WorkspaceError
from app.main import _authorize_staff_action

OWNER = {"id": 1, "role": "owner", "login": "owner", "display_name": "Owner"}


def test_import_creates_zero_stock_and_preserves_barcode():
    state = default_state()
    apply_action(state, OWNER, "ingredient.import", {"items": [{"name": "Импорт тест", "category": "Сырьё", "unit": "кг", "barcode": "12345", "limit": 2}]})
    item = next(i for i in state["ingredients"] if i["name"] == "Импорт тест")
    assert item["barcode"] == "12345"
    assert item["limit"] == 2
    assert all(stock.get(item["id"], 0) == 0 for stock in state["logisticsState"]["branchStocks"].values())
    apply_action(state, OWNER, "catalog.delete", {"kind": "ingredient", "id": item["id"]})
    assert item not in state["ingredients"]


def test_import_is_atomic_when_last_row_invalid():
    state = default_state()
    original = deepcopy(state["ingredients"])
    with pytest.raises(WorkspaceError):
        apply_action(state, OWNER, "ingredient.import", {"items": [{"name": "Новый 1", "unit": "кг"}, {"name": "Новый 2", "unit": "неизвестно"}]})
    assert state["ingredients"] == original


def test_import_rejects_duplicates_and_cashiers():
    state = default_state()
    with pytest.raises(WorkspaceError):
        apply_action(state, OWNER, "ingredient.import", {"items": [{"name": state["ingredients"][0]["name"], "unit": "кг"}]})
    with pytest.raises(Exception) as denied:
        _authorize_staff_action({"role": "branch", "staff_role": "cashier", "access_permissions": {}}, "ingredient.import")
    assert denied.value.status_code == 403


def test_delete_ingredient_removes_recipe_and_preparation_components():
    state = default_state()
    apply_action(state, OWNER, "ingredient.import", {"items": [{"name": "Стакан тест", "unit": "шт"}]})
    item = next(i for i in state["ingredients"] if i["name"] == "Стакан тест")
    component = {"ingredientId": item["id"], "quantity": 1}
    recipe = state["recipes"][0]
    original = deepcopy(recipe["components"])
    recipe["components"].append(component.copy())
    state.setdefault("preparations", []).append({"id": "delete-test", "name": "П/ф", "components": [component.copy()]})
    documents = deepcopy(state["logisticsState"])
    apply_action(state, OWNER, "catalog.delete", {"kind": "ingredient", "id": item["id"]})
    assert item not in state["ingredients"]
    assert recipe["components"] == original
    assert state["preparations"][-1]["components"] == []
    for key, value in documents.items():
        if key not in {"branchStocks", "branchCosts"}:
            assert state["logisticsState"][key] == value


def test_product_cover_and_markup_persist_and_reject_unsafe_image():
    state = default_state()
    payload = {"id": "cover-test", "name": "Фото товар", "price": 150, "averageCost": 100, "color": "#336699", "markup": 50, "image": "data:image/png;base64,iVBORw0KGgo="}
    apply_action(state, OWNER, "product.upsert", payload)
    item = next(i for i in state["products"] if i["id"] == "cover-test")
    assert item["image"] == payload["image"] and item["color"] == "#336699" and item["markup"] == 50
    with pytest.raises(WorkspaceError):
        apply_action(state, OWNER, "product.upsert", {**payload, "image": "javascript:alert(1)"})
