from decimal import Decimal

import pytest

from app.domain import DomainError, calculate_unit_costs, find_cycle


def test_nested_preparation_cost_is_included_in_product() -> None:
    costs = calculate_unit_costs(
        {"flour": Decimal("54"), "salt": Decimal("30"), "dough": Decimal("0"), "lagman": Decimal("0")},
        {
            "dough": (Decimal("1"), [("flour", Decimal("0.95")), ("salt", Decimal("0.02"))]),
            "lagman": (Decimal("1"), [("dough", Decimal("0.15"))]),
        },
    )

    assert costs["dough"] == Decimal("51.90")
    assert costs["lagman"] == Decimal("7.7850")


def test_cycle_path_is_reported() -> None:
    cycle = find_cycle("dough", ["starter"], {"starter": ["dough"]})
    assert cycle == ["dough", "starter", "dough"]


def test_cost_calculation_rejects_corrupted_cycle() -> None:
    with pytest.raises(DomainError):
        calculate_unit_costs(
            {"a": Decimal("0"), "b": Decimal("0")},
            {"a": (Decimal("1"), [("b", Decimal("1"))]), "b": (Decimal("1"), [("a", Decimal("1"))])},
        )

