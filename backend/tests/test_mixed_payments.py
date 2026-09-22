from copy import deepcopy
from decimal import Decimal

import pytest

from app.workspace import (WorkspaceError, apply_action, default_state,
                           normalize_sale_payments, sale_payment_amount, visible_state)
from custody_helpers import accepted_transfer

USER = {"id": 2, "login": "manasa", "role": "branch", "branch_id": "b1", "display_name": "Cashier", "staff_role": "branch_manager", "shift_id": 20}


def test_three_tenders_cash_change_is_excluded_from_revenue():
    parts, method, received, change = normalize_sale_payments({"payments": [
        {"method": "cash", "amount": 200}, {"method": "card", "amount": 150}, {"method": "qr", "amount": 160}
    ]}, 460)
    assert method == "mixed" and received == 510 and change == 50
    assert sum(part["amount"] for part in parts) == 460
    assert sale_payment_amount({"payments": parts}, "cash") == Decimal(150)
    assert sale_payment_amount({"paymentMethod": "cash", "total": 460}, "cash") == Decimal(460)


@pytest.mark.parametrize("payments", [
    [], [{"method":"card", "amount":461}],
    [{"method":"cash", "amount":100}, {"method":"qr", "amount":100}],
    [{"method":"cash", "amount":460}, {"method":"cash", "amount":1}],
    [{"method":"cash", "amount":-10}, {"method":"card", "amount":470}],
    [{"method":"cash", "amount":"NaN"}], [{"method":"qr", "amount":"Infinity"}],
    [{"method":"cash", "amount":460.001}], [{"method":"other", "amount":460}],
    [{"method":[], "amount":460}], [{"method":"cash", "amount":True}],
])
def test_invalid_splits_rejected(payments):
    with pytest.raises(WorkspaceError):
        normalize_sale_payments({"payments":payments}, 460)


def test_decimal_parts_do_not_produce_false_change():
    parts, method, received, change = normalize_sale_payments({"payments":[
        {"method":"card", "amount":0.1}, {"method":"qr", "amount":0.2}]}, 0.3)
    assert method == "mixed" and received == 0.3 and change == 0


def test_mixed_sale_visible_and_refund_preserves_tenders():
    state = default_state()
    apply_action(state, USER, "batch.create", {"recipeId":201, "weight":0.76})
    batch = state["logisticsState"]["batches"][0]
    accepted_transfer(state, USER, {"id":batch["id"], "weight":0.76, "temperature":65, "line":"Line"})
    payload = {"items":[{"id":201,"quantity":2}], "payments":[{"method":"cash","amount":200},{"method":"qr","amount":310}]}
    before = deepcopy(state)
    with pytest.raises(WorkspaceError):
        apply_action(state, USER, "sale.create", {**payload,"payments":[{"method":"cash","amount":1}]})
    assert state["sales"] == before["sales"]
    assert batch["soldPortions"] == before["logisticsState"]["batches"][0]["soldPortions"]
    _, sale_id = apply_action(state, USER, "sale.create", payload)
    sale = state["sales"][0]
    assert sale["change"] == 50 and sale["paymentMethod"] == "mixed"
    assert sale_payment_amount(sale,"cash") == Decimal(150)
    shown = visible_state(state, USER)
    assert next(s for s in shown["sales"] if s["id"] == sale_id)["payments"] == sale["payments"]
    parts = deepcopy(sale["payments"])
    apply_action(state, USER, "sale.refund", {"id":sale_id,"reason":"Return"})
    assert sale["payments"] == parts and sale["refundedAt"]
