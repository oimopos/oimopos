from datetime import datetime, timezone

from app.demo_data import build_buffet_demo_state, demo_state_summary
from app.workspace import visible_state


def existing_state() -> dict:
    return {
        "schemaVersion": 2,
        "branches": [{"id": "b1", "number": 1, "short": "Buffet 1", "name": "Buffet 1", "address": "Токтогула 112", "status": "active"}],
    }


def test_buffet_demo_is_complete_and_preserves_location() -> None:
    state = build_buffet_demo_state(existing_state(), now=datetime(2026, 9, 19, tzinfo=timezone.utc))
    summary = demo_state_summary(state)

    assert state["branches"][0]["name"] == "Buffet 1"
    assert state["branches"][0]["address"] == "Токтогула 112"
    assert summary == {
        "branches": 1, "ingredientCategories": 12, "menuCategories": 8, "ingredients": 36,
        "products": 8, "recipes": 18, "preparations": 6, "stations": 4, "suppliers": 5,
        "receipts": 5, "batches": 18, "sales": 14, "financeTransactions": 7,
    }


def test_demo_references_yields_prices_and_balances_are_consistent() -> None:
    state = build_buffet_demo_state(existing_state(), now=datetime(2026, 9, 19, tzinfo=timezone.utc))
    ingredient_ids = {item["id"] for item in state["ingredients"]}
    entity_ids = ingredient_ids | {item["id"] for item in state["products"]}
    menu_categories = {category["name"] for category in state["menuCategories"]}
    stocks = state["logisticsState"]["branchStocks"]["b1"]
    costs = state["logisticsState"]["branchCosts"]["b1"]

    assert set(stocks) == entity_ids == set(costs)
    assert all(component["ingredientId"] in ingredient_ids for recipe in state["recipes"] for component in recipe["components"])
    assert all(recipe["yield"] == sum(component["net"] for component in recipe["components"]) for recipe in state["recipes"])
    assert all(preparation["yield"] == sum(component["net"] for component in preparation["components"]) for preparation in state["preparations"])
    assert all(recipe["category"] in menu_categories for recipe in state["recipes"])
    assert all(product["category"] in menu_categories for product in state["products"])
    assert all(ingredient["category"] in set(state["ingredientCategories"]) for ingredient in state["ingredients"])
    assert all(supplier["locations"] == ["b1"] and supplier["prices"]["b1"] for supplier in state["suppliers"])
    assert set().union(*(set(supplier["prices"]["b1"]) for supplier in state["suppliers"])) == entity_ids
    assert all(batch["soldPortions"] < int(batch["transferredWeight"] * 1000 / next(recipe["yield"] for recipe in state["recipes"] if recipe["id"] == batch["recipeId"])) for batch in state["logisticsState"]["batches"])


def test_demo_remains_safe_for_cashier_workspace() -> None:
    state = build_buffet_demo_state(existing_state(), now=datetime(2026, 9, 19, tzinfo=timezone.utc))
    cashier = {"id": 3, "login": "terminal", "role": "branch", "staff_role": "pos_terminal", "branch_id": "b1", "display_name": "Основная касса"}

    visible = visible_state(state, cashier)

    assert visible["ingredients"] == []
    assert visible["suppliers"] == []
    assert len(visible["recipes"]) == 18
    assert len(visible["products"]) == 8
    assert all("unitCost" not in item for sale in visible["sales"] for item in sale["items"])
