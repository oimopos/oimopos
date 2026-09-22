from decimal import Decimal


class DomainError(ValueError):
    pass


def find_cycle(output_item_id: str, component_ids: list[str], adjacency: dict[str, list[str]]) -> list[str] | None:
    graph = {item_id: list(children) for item_id, children in adjacency.items()}
    graph[output_item_id] = component_ids

    def visit(item_id: str, path: list[str], active: set[str]) -> list[str] | None:
        if item_id in active:
            start = path.index(item_id)
            return path[start:] + [item_id]
        active.add(item_id)
        path.append(item_id)
        for child_id in graph.get(item_id, []):
            cycle = visit(child_id, path, active)
            if cycle:
                return cycle
        path.pop()
        active.remove(item_id)
        return None

    return visit(output_item_id, [], set())


def calculate_unit_costs(
    purchase_costs: dict[str, Decimal],
    cards: dict[str, tuple[Decimal, list[tuple[str, Decimal]]]],
) -> dict[str, Decimal]:
    memo: dict[str, Decimal] = {}

    def cost(item_id: str, active: set[str]) -> Decimal:
        if item_id in memo:
            return memo[item_id]
        if item_id in active:
            raise DomainError(f"Цикл в техкартах: {item_id}")
        if item_id not in cards:
            value = purchase_costs.get(item_id, Decimal("0"))
            memo[item_id] = value
            return value

        active.add(item_id)
        yield_quantity, components = cards[item_id]
        total = sum((quantity * cost(component_id, active) for component_id, quantity in components), Decimal("0"))
        active.remove(item_id)
        value = total / yield_quantity
        memo[item_id] = value
        return value

    for catalog_item_id in purchase_costs:
        cost(catalog_item_id, set())
    return memo

