from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any


def _ingredient(
    item_id: str, name: str, category: str, unit: str, cost: float, stock: float, limit: float,
    *, losses: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "name": name,
        "category": category,
        "unit": unit,
        "stock": 0,
        "averageCost": cost,
        "limit": limit,
        "losses": losses or {"clean": 0, "boil": 0, "fry": 0, "bake": 0},
        "demoStock": stock,
    }


def _component(item_id: str, net: float, gross: float | None = None, measure: str | None = None) -> dict[str, Any]:
    component: dict[str, Any] = {"ingredientId": item_id, "gross": gross if gross is not None else net, "net": net}
    if measure:
        component["measure"] = measure
    return component


def _recipe(
    recipe_id: int, name: str, category: str, price: float, color: str, station: str,
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": recipe_id,
        "name": name,
        "category": category,
        "price": price,
        "color": color,
        "yield": sum(float(component["net"]) for component in components),
        "station": station,
        "components": components,
    }


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def build_buffet_demo_state(existing_state: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Build a complete, internally consistent demo workspace while preserving the tenant location."""
    now = now or datetime.now(timezone.utc)
    branches = deepcopy(existing_state.get("branches") or [])
    if not branches:
        raise ValueError("У аккаунта нет заведения")
    branch = branches[0]
    branch_id = str(branch["id"])
    branch_name = str(branch["name"])

    ingredients = [
        _ingredient("rice", "Рис лазер", "Крупы и макароны", "кг", 96, 68, 20),
        _ingredient("buckwheat", "Крупа гречневая", "Крупы и макароны", "кг", 110, 28, 8),
        _ingredient("pasta", "Макароны", "Крупы и макароны", "кг", 88, 24, 8),
        _ingredient("beans", "Чечевица красная", "Крупы и макароны", "кг", 145, 18, 6),
        _ingredient("flour", "Мука высший сорт", "Бакалея", "кг", 54, 76, 20),
        _ingredient("sugar", "Сахар", "Бакалея", "кг", 82, 32, 10),
        _ingredient("salt", "Соль", "Специи", "кг", 30, 8, 2),
        _ingredient("spices", "Смесь специй", "Специи", "кг", 760, 2.4, 0.7),
        _ingredient("yeast", "Дрожжи сухие", "Бакалея", "кг", 420, 1.8, 0.5),
        _ingredient("oil", "Масло растительное", "Бакалея", "л", 145, 24, 8),
        _ingredient("water", "Вода питьевая", "Напитки", "л", 8, 120, 30),
        _ingredient("beef", "Говядина", "Мясо", "кг", 520, 38, 12, losses={"clean": 8, "boil": 28, "fry": 32, "bake": 25}),
        _ingredient("lamb", "Баранина", "Мясо", "кг", 590, 24, 8, losses={"clean": 9, "boil": 30, "fry": 34, "bake": 27}),
        _ingredient("chicken", "Куриное филе", "Мясо", "кг", 260, 31, 10, losses={"clean": 5, "boil": 22, "fry": 25, "bake": 20}),
        _ingredient("sausage", "Колбаса варёная", "Мясо", "кг", 310, 12, 4),
        _ingredient("fish", "Филе судака", "Рыба", "кг", 480, 16, 5, losses={"clean": 6, "boil": 18, "fry": 22, "bake": 17}),
        _ingredient("potato", "Картофель", "Овощи", "кг", 48, 74, 20, losses={"clean": 18, "boil": 3, "fry": 28, "bake": 12}),
        _ingredient("carrot", "Морковь", "Овощи", "кг", 55, 29, 8, losses={"clean": 12, "boil": 8, "fry": 15, "bake": 10}),
        _ingredient("onion", "Лук репчатый", "Овощи", "кг", 45, 26, 8, losses={"clean": 14, "boil": 9, "fry": 18, "bake": 12}),
        _ingredient("tomato", "Помидоры", "Овощи", "кг", 130, 23, 7, losses={"clean": 4, "boil": 14, "fry": 18, "bake": 12}),
        _ingredient("cucumber", "Огурцы", "Овощи", "кг", 105, 19, 6, losses={"clean": 3, "boil": 0, "fry": 0, "bake": 0}),
        _ingredient("cabbage", "Капуста белокочанная", "Овощи", "кг", 42, 27, 8, losses={"clean": 16, "boil": 12, "fry": 14, "bake": 10}),
        _ingredient("pepper", "Перец болгарский", "Овощи", "кг", 190, 11, 4, losses={"clean": 12, "boil": 15, "fry": 20, "bake": 17}),
        _ingredient("garlic", "Чеснок", "Овощи", "кг", 210, 4.5, 1.5, losses={"clean": 10, "boil": 8, "fry": 12, "bake": 10}),
        _ingredient("greens", "Зелень свежая", "Зелень", "кг", 280, 5.2, 1.5, losses={"clean": 8, "boil": 20, "fry": 24, "bake": 18}),
        _ingredient("lemon", "Лимон", "Фрукты", "кг", 220, 8, 2, losses={"clean": 25, "boil": 0, "fry": 0, "bake": 0}),
        _ingredient("dried_fruit", "Сухофрукты", "Фрукты", "кг", 330, 9, 3),
        _ingredient("milk", "Молоко 3,2%", "Молочные продукты", "л", 78, 24, 8),
        _ingredient("butter", "Масло сливочное", "Молочные продукты", "кг", 620, 7.5, 2.5),
        _ingredient("sour_cream", "Сметана", "Молочные продукты", "кг", 260, 9, 3),
        _ingredient("cheese", "Сыр твёрдый", "Молочные продукты", "кг", 690, 8, 2.5),
        _ingredient("egg", "Яйцо куриное", "Яйца", "кг", 240, 36, 10),
        _ingredient("mayonnaise", "Майонез", "Соусы", "кг", 210, 12, 4),
        _ingredient("tea", "Чай чёрный", "Напитки", "кг", 680, 2.2, 0.8),
        _ingredient("coffee", "Кофе зерновой", "Напитки", "кг", 1450, 3.5, 1),
        _ingredient("cocoa", "Какао", "Напитки", "кг", 760, 2, 0.6),
    ]

    products = [
        {"id": "p-1", "name": "Вода 0,5 л", "category": "Напитки", "barcode": "4860001123456", "averageCost": 28, "price": 50, "stock": 0, "unit": "шт", "limit": 24, "demoStock": 96},
        {"id": "p-2", "name": "Coca-Cola 0,5 л", "category": "Напитки", "barcode": "5449000054227", "averageCost": 52, "price": 90, "stock": 0, "unit": "шт", "limit": 18, "demoStock": 58},
        {"id": "p-3", "name": "Сок яблочный 0,2 л", "category": "Напитки", "barcode": "4860012345678", "averageCost": 36, "price": 65, "stock": 0, "unit": "шт", "limit": 12, "demoStock": 42},
        {"id": "p-4", "name": "Айран 0,3 л", "category": "Напитки", "barcode": "4860043217654", "averageCost": 32, "price": 60, "stock": 0, "unit": "шт", "limit": 15, "demoStock": 47},
        {"id": "p-5", "name": "Шоколад молочный", "category": "Сладости", "barcode": "4607065000781", "averageCost": 45, "price": 75, "stock": 0, "unit": "шт", "limit": 8, "demoStock": 25},
        {"id": "p-6", "name": "Печенье овсяное", "category": "Сладости", "barcode": "4860067890123", "averageCost": 38, "price": 65, "stock": 0, "unit": "шт", "limit": 10, "demoStock": 31},
        {"id": "p-7", "name": "Салфетки влажные", "category": "Дополнительно", "barcode": "4860098765432", "averageCost": 12, "price": 25, "stock": 0, "unit": "шт", "limit": 25, "demoStock": 120},
        {"id": "p-8", "name": "Жевательная резинка", "category": "Дополнительно", "barcode": "4601234567890", "averageCost": 18, "price": 35, "stock": 0, "unit": "шт", "limit": 15, "demoStock": 44},
    ]

    recipes = [
        _recipe(101, "Плов фирменный", "Горячие блюда", 250, "#e39a3d", "Горячий цех", [
            _component("rice", 150), _component("beef", 100, 115), _component("carrot", 70, 82),
            _component("onion", 30, 35), _component("oil", 25, measure="мл"), _component("salt", 3), _component("spices", 2),
        ]),
        _recipe(102, "Лагман домашний", "Горячие блюда", 270, "#bd6557", "Горячий цех", [
            _component("beef", 110, 130), _component("flour", 160), _component("onion", 40, 45),
            _component("tomato", 80, 90), _component("pepper", 30, 35), _component("oil", 18, measure="мл"),
            _component("spices", 2), _component("salt", 2), _component("water", 8, measure="мл"),
        ]),
        _recipe(103, "Шорпо с говядиной", "Первые блюда", 230, "#62a56f", "Горячий цех", [
            _component("beef", 100, 120), _component("potato", 125, 150), _component("carrot", 30, 35),
            _component("onion", 26, 30), _component("salt", 3), _component("spices", 1), _component("water", 135, measure="мл"),
        ]),
        _recipe(104, "Курица с картофелем", "Горячие блюда", 220, "#cc7c58", "Горячий цех", [
            _component("chicken", 200, 230), _component("potato", 110, 135), _component("oil", 10, measure="мл"),
            _component("salt", 4), _component("spices", 6),
        ]),
        _recipe(105, "Котлета с гречкой", "Горячие блюда", 240, "#8a745d", "Горячий цех", [
            _component("beef", 120, 140), _component("buckwheat", 150), _component("onion", 25, 30),
            _component("oil", 15, measure="мл"), _component("salt", 3), _component("spices", 2), _component("water", 5, measure="мл"),
        ]),
        _recipe(106, "Судак запечённый", "Горячие блюда", 290, "#5b8fbd", "Горячий цех", [
            _component("fish", 200, 220), _component("potato", 120, 145), _component("oil", 10, measure="мл"),
            _component("lemon", 20, 27), _component("salt", 3), _component("spices", 2),
        ]),
        _recipe(107, "Манты с бараниной", "Горячие блюда", 260, "#9d6f56", "Горячий цех", [
            _component("lamb", 150, 170), _component("flour", 130), _component("onion", 35, 40),
            _component("oil", 10, measure="мл"), _component("salt", 3), _component("spices", 2), _component("water", 70, measure="мл"),
        ]),
        _recipe(108, "Борщ со сметаной", "Первые блюда", 210, "#b9504e", "Горячий цех", [
            _component("beef", 80, 95), _component("cabbage", 100, 120), _component("potato", 80, 98),
            _component("carrot", 30, 35), _component("onion", 25, 30), _component("tomato", 55, 65),
            _component("oil", 10, measure="мл"), _component("sour_cream", 15), _component("salt", 5), _component("water", 100, measure="мл"),
        ]),
        _recipe(109, "Чечевичный суп", "Первые блюда", 180, "#d27646", "Горячий цех", [
            _component("beans", 80), _component("potato", 80, 98), _component("carrot", 30, 35),
            _component("onion", 25, 30), _component("oil", 10, measure="мл"), _component("salt", 5), _component("water", 270, measure="мл"),
        ]),
        _recipe(110, "Салат свежий", "Салаты", 120, "#4e9b8d", "Холодный цех", [
            _component("tomato", 145, 155), _component("cucumber", 100, 104), _component("onion", 30, 35),
            _component("oil", 15, measure="мл"), _component("greens", 5, 6), _component("salt", 5),
        ]),
        _recipe(111, "Салат Оливье", "Салаты", 170, "#6a9d68", "Холодный цех", [
            _component("potato", 100, 122), _component("carrot", 50, 58), _component("egg", 50, 55),
            _component("sausage", 50), _component("cucumber", 50, 52), _component("mayonnaise", 30), _component("salt", 2),
        ]),
        _recipe(112, "Ачичук", "Салаты", 100, "#cf6657", "Холодный цех", [
            _component("tomato", 120, 130), _component("onion", 35, 42), _component("greens", 5, 6), _component("salt", 2),
        ]),
        _recipe(113, "Самса с мясом", "Выпечка", 95, "#c98b45", "Пекарня", [
            _component("flour", 120), _component("lamb", 80, 92), _component("onion", 40, 47),
            _component("oil", 10, measure="мл"), _component("salt", 3), _component("spices", 2), _component("water", 45, measure="мл"),
        ]),
        _recipe(114, "Булочка сдобная", "Выпечка", 65, "#d6a766", "Пекарня", [
            _component("flour", 120), _component("milk", 50, measure="мл"), _component("butter", 15),
            _component("sugar", 20), _component("yeast", 5), _component("egg", 30, 33), _component("water", 10, measure="мл"),
        ]),
        _recipe(115, "Компот из сухофруктов", "Напитки", 60, "#a76557", "Бар", [
            _component("water", 250, measure="мл"), _component("sugar", 25), _component("lemon", 15, 20), _component("dried_fruit", 30),
        ]),
        _recipe(116, "Чай с лимоном", "Напитки", 50, "#987347", "Бар", [
            _component("water", 250, measure="мл"), _component("tea", 5), _component("sugar", 15), _component("lemon", 10, 14),
        ]),
        _recipe(117, "Кофе с молоком", "Напитки", 110, "#725448", "Бар", [
            _component("water", 180, measure="мл"), _component("coffee", 10), _component("milk", 50, measure="мл"), _component("sugar", 10),
        ]),
        _recipe(118, "Омлет с сыром", "Завтраки", 180, "#d6b94d", "Горячий цех", [
            _component("egg", 120, 132), _component("milk", 60, measure="мл"), _component("butter", 10), _component("cheese", 30), _component("salt", 2),
        ]),
    ]

    preparations = [
        {"id": "pf-1", "name": "Тесто для лагмана", "category": "Тесто", "station": "Горячий цех", "yield": 1000, "usedIn": "Лагман домашний", "process": "Замесить до эластичности, выдержать 30 минут и вытянуть лапшу.", "components": [_component("flour", 760), _component("egg", 100, 110), _component("water", 122, measure="мл"), _component("salt", 18)]},
        {"id": "pf-2", "name": "Бульон говяжий", "category": "Бульоны", "station": "Горячий цех", "yield": 5000, "usedIn": "Шорпо, борщ", "process": "Варить на слабом огне 3 часа, процедить и быстро охладить.", "components": [_component("beef", 900, 1050), _component("carrot", 200, 230), _component("onion", 200, 235), _component("water", 3680, measure="мл"), _component("salt", 20)]},
        {"id": "pf-3", "name": "Заправка салатная", "category": "Соусы и заправки", "station": "Холодный цех", "yield": 800, "usedIn": "Свежие салаты", "process": "Смешать ингредиенты до однородности, хранить при +2…+6 °C.", "components": [_component("oil", 650, measure="мл"), _component("lemon", 120, 160), _component("salt", 20), _component("spices", 10)]},
        {"id": "pf-4", "name": "Зирвак для плова", "category": "Заготовки кухни", "station": "Горячий цех", "yield": 3000, "usedIn": "Плов фирменный", "process": "Обжарить мясо и овощи, добавить специи и томить 45 минут.", "components": [_component("beef", 1100, 1265), _component("carrot", 900, 1050), _component("onion", 450, 525), _component("oil", 400, measure="мл"), _component("water", 120, measure="мл"), _component("spices", 20), _component("salt", 10)]},
        {"id": "pf-5", "name": "Тесто для мантов", "category": "Тесто", "station": "Горячий цех", "yield": 2000, "usedIn": "Манты с бараниной", "process": "Замесить крутое тесто и выдержать под плёнкой 40 минут.", "components": [_component("flour", 1350), _component("egg", 200, 220), _component("water", 424, measure="мл"), _component("salt", 26)]},
        {"id": "pf-6", "name": "Основа для компота", "category": "Напитки", "station": "Бар", "yield": 5000, "usedIn": "Компот из сухофруктов", "process": "Промыть сухофрукты, варить 25 минут и настоять до охлаждения.", "components": [_component("water", 4400, measure="мл"), _component("dried_fruit", 400), _component("sugar", 180), _component("lemon", 20, 28)]},
    ]

    menu_categories = [
        {"name": "Завтраки", "color": "#d6b94d"}, {"name": "Первые блюда", "color": "#62a56f"},
        {"name": "Горячие блюда", "color": "#e39a3d"}, {"name": "Салаты", "color": "#4e9b8d"},
        {"name": "Выпечка", "color": "#c98b45"}, {"name": "Напитки", "color": "#5b8fbd"},
        {"name": "Сладости", "color": "#7b69d4"}, {"name": "Дополнительно", "color": "#7d8a90"},
    ]
    ingredient_categories = [
        "Крупы и макароны", "Мясо", "Рыба", "Овощи", "Зелень", "Фрукты", "Молочные продукты",
        "Яйца", "Бакалея", "Специи", "Соусы", "Напитки",
    ]

    ingredient_by_id = {item["id"]: item for item in ingredients}
    product_by_id = {item["id"]: item for item in products}
    entity_by_id = {**ingredient_by_id, **product_by_id}
    costs = {item_id: float(item["averageCost"]) for item_id, item in entity_by_id.items()}
    stocks = {item_id: float(item.pop("demoStock")) for item_id, item in entity_by_id.items()}

    supplier_specs = [
        ("supplier-farm", "Фермерские продукты", "01209202610011", "Эльмира", "+996 555 410 410", "orders@farm.kg", "Бишкек, ул. Логвиненко, 55", "Овощи, зелень и фрукты", ["potato", "carrot", "onion", "tomato", "cucumber", "cabbage", "pepper", "garlic", "greens", "lemon", "dried_fruit"]),
        ("supplier-meat", "Мясной стандарт", "01209202610022", "Нурбек", "+996 700 520 520", "sales@meat.kg", "Бишкек, ул. Фрунзе, 188", "Мясо, птица и рыба", ["beef", "lamb", "chicken", "sausage", "fish"]),
        ("supplier-grocery", "Бакалея Сервис", "01209202610033", "Айжан", "+996 777 630 630", "zakaz@grocery.kg", "Бишкек, рынок Дордой-Моторс", "Бакалея и специи, доставка пн–сб", ["rice", "buckwheat", "pasta", "beans", "flour", "sugar", "salt", "spices", "yeast", "oil", "water", "tea", "coffee", "cocoa"]),
        ("supplier-dairy", "Молочный дом", "01209202610044", "Отдел HoReCa", "+996 555 740 740", "horeca@milk.kg", "Бишкек, ул. Матросова, 4", "Молочная продукция и яйца", ["milk", "butter", "sour_cream", "cheese", "egg", "mayonnaise"]),
        ("supplier-drinks", "Напитки Оптом", "01209202610055", "Каныбек", "+996 700 850 850", "order@drinks.kg", "Бишкек, ул. Интергельпо, 1", "Готовые напитки и сопутствующие товары", list(product_by_id)),
    ]
    suppliers = []
    for supplier_id, name, inn, contact, phone, email, address, comment, item_ids in supplier_specs:
        suppliers.append({
            "id": supplier_id, "name": name, "inn": inn, "contact": contact, "phone": phone, "email": email,
            "address": address, "comment": comment, "status": "active", "locations": [branch_id],
            "prices": {branch_id: {item_id: costs[item_id] for item_id in item_ids}},
        })

    def order(number: int, supplier_id: str, item_quantities: list[tuple[str, float]], days_ago: int, invoice: str) -> dict[str, Any]:
        supplier = next(item for item in suppliers if item["id"] == supplier_id)
        received_at = now - timedelta(days=days_ago)
        created_at = received_at - timedelta(days=1)
        rows = []
        for item_id, quantity in item_quantities:
            price = costs[item_id]
            rows.append({"itemId": item_id, "requested": quantity, "estimatedPrice": price, "received": quantity, "receivedPrice": price, "temperature": 4 if entity_by_id[item_id]["category"] in {"Мясо", "Рыба", "Молочные продукты", "Яйца"} else 18})
        return {
            "id": f"demo-order-{number}", "number": f"ЗП-{number:04d}", "branchId": branch_id,
            "supplierId": supplier_id, "supplier": supplier["name"], "neededAt": received_at.date().isoformat(),
            "comment": "Плановое пополнение", "items": rows, "total": sum(row["received"] * row["receivedPrice"] for row in rows),
            "status": "received", "createdAt": _iso(created_at), "createdBy": "Айбек Управляющий",
            "approvedAt": _iso(created_at + timedelta(hours=1)), "approvedBy": "daison",
            "orderedAt": _iso(created_at + timedelta(hours=2)), "orderedBy": "Айбек Управляющий", "sentVia": "email",
            "receivedAt": _iso(received_at), "receivedBy": "Айбек Управляющий", "invoiceNumber": invoice,
            "receivingComment": "Количество и качество проверены", "variance": 0,
        }

    direct_orders = [
        order(5, "supplier-drinks", [("p-1", 72), ("p-2", 36), ("p-3", 30), ("p-4", 30)], 2, "НП-0905"),
        order(4, "supplier-farm", [("potato", 45), ("carrot", 18), ("onion", 18), ("tomato", 15), ("cucumber", 12)], 4, "ФП-1842"),
        order(3, "supplier-meat", [("beef", 24), ("lamb", 14), ("chicken", 20), ("fish", 10)], 7, "МС-7714"),
        order(2, "supplier-dairy", [("milk", 18), ("butter", 5), ("sour_cream", 6), ("cheese", 5), ("egg", 120)], 10, "МД-3308"),
        order(1, "supplier-grocery", [("rice", 50), ("flour", 50), ("oil", 20), ("sugar", 20), ("tea", 2)], 14, "БС-5411"),
    ]
    supplies = [{
        **entry,
        "documentType": "supply",
        "paidTotal": entry["total"],
        "debt": 0,
        "payments": [],
        "paymentStatus": "paid",
    } for entry in direct_orders]

    recipe_by_id = {recipe["id"]: recipe for recipe in recipes}

    def recipe_cost(recipe: dict[str, Any]) -> float:
        return round(sum(costs[component["ingredientId"]] * float(component["net"]) / 1000 for component in recipe["components"]), 2)

    sale_specs = [
        (0, "Алия", "card", [(101, 2), (110, 1), ("p-1", 2)]),
        (0, "Бекжан", "cash", [(104, 2), (115, 2), ("p-5", 1)]),
        (1, "Алия", "qr", [(107, 3), (112, 2), (116, 2)]),
        (1, "Бекжан", "card", [(102, 2), (111, 1), ("p-2", 2)]),
        (2, "Алия", "cash", [(103, 3), (113, 3), (115, 2)]),
        (2, "Бекжан", "qr", [(105, 2), (110, 2), ("p-4", 2)]),
        (3, "Алия", "card", [(108, 2), (114, 3), (116, 2)]),
        (3, "Бекжан", "cash", [(101, 3), (112, 2), ("p-1", 3)]),
        (4, "Алия", "qr", [(106, 2), (110, 1), (117, 2)]),
        (4, "Бекжан", "card", [(109, 3), (113, 2), ("p-3", 2)]),
        (5, "Алия", "cash", [(118, 2), (114, 2), (117, 2)]),
        (5, "Бекжан", "card", [(104, 3), (111, 2), ("p-2", 2)]),
        (6, "Алия", "qr", [(102, 3), (112, 2), (115, 3)]),
        (6, "Бекжан", "cash", [(101, 2), (103, 2), ("p-1", 2)]),
    ]
    sales = []
    sold_portions: dict[int, int] = {recipe_id: 0 for recipe_id in recipe_by_id}
    for index, (days_ago, cashier, payment, lines) in enumerate(sale_specs, start=1):
        sale_items = []
        total = 0.0
        for item_id, quantity in lines:
            if isinstance(item_id, int):
                item = recipe_by_id[item_id]
                unit_cost = recipe_cost(item)
                unit = "порция"
                sold_portions[item_id] += int(quantity)
            else:
                item = product_by_id[item_id]
                unit_cost = costs[item_id]
                unit = item["unit"]
            sale_items.append({"id": item_id, "name": item["name"], "category": item["category"], "unit": unit, "price": item["price"], "unitCost": unit_cost, "quantity": quantity})
            total += float(item["price"]) * quantity
        created_at = now - timedelta(days=days_ago, hours=2 + index % 8)
        received = total if payment != "cash" else float((int(total + 499) // 500) * 500)
        sales.append({
            "id": f"demo-sale-{index}", "number": 1000 + index, "branchId": branch_id, "branch": branch_name,
            "cashier": cashier, "createdAt": _iso(created_at), "paymentMethod": payment, "total": total,
            "received": received, "change": received - total, "items": sale_items,
        })
    sales.sort(key=lambda sale: sale["createdAt"], reverse=True)

    batches = []
    for index, recipe in enumerate(recipes, start=1):
        capacity = sold_portions[recipe["id"]] + 12
        weight = round(float(recipe["yield"]) / 1000 * capacity, 3)
        batches.append({
            "id": f"demo-batch-{recipe['id']}", "number": f"АП-{index:04d}", "branchId": branch_id,
            "recipeId": recipe["id"], "actualWeight": weight, "transferredWeight": weight,
            "soldPortions": sold_portions[recipe["id"]], "servedPortions": sold_portions[recipe["id"]],
            "status": "serving", "createdAt": _iso(now - timedelta(hours=8)), "createdBy": "Повар смены",
            "cost": round(recipe_cost(recipe) * capacity, 2),
            "servingTemperature": 7 if recipe["category"] == "Салаты" else 65,
            "servingLine": "Холодная витрина" if recipe["category"] == "Салаты" else "Линия раздачи №1",
            "servingReceiver": "Бекжан", "transferredAt": _iso(now - timedelta(hours=6)), "transferredBy": "Повар смены",
        })

    ledger = []
    for order_entry in direct_orders:
        for row in order_entry["items"]:
            ledger.append({
                "id": f"ledger-{order_entry['id']}-{row['itemId']}", "branchId": branch_id, "itemId": row["itemId"],
                "quantity": row["received"], "unitCost": row["receivedPrice"], "movementType": "supplier_receipt",
                "documentNumber": order_entry["number"], "createdAt": order_entry["receivedAt"], "createdBy": order_entry["receivedBy"],
            })
    ledger.sort(key=lambda entry: entry["createdAt"], reverse=True)

    inventory_items = []
    for item_id in [item["id"] for item in ingredients if item["category"] == "Крупы и макароны"]:
        inventory_items.append({"itemId": item_id, "book": stocks[item_id], "actual": stocks[item_id], "unitCost": costs[item_id]})
    inventories = [{
        "id": "demo-inventory-1", "number": "ИНВ-0001", "branchId": branch_id, "scope": "category",
        "category": "Крупы и макароны", "responsible": "Айбек Управляющий", "status": "posted", "items": inventory_items,
        "comment": "Плановая контрольная инвентаризация", "reviewComment": "Расхождений нет",
        "createdAt": _iso(now - timedelta(days=9)), "createdBy": "Айбек Управляющий",
        "submittedAt": _iso(now - timedelta(days=9, hours=-1)), "submittedBy": "Айбек Управляющий",
        "postedAt": _iso(now - timedelta(days=9, hours=-2)), "postedBy": "daison",
    }]

    finance_categories = [
        {"id": "finance-income-other", "name": "Прочие доходы", "kind": "income", "status": "active"},
        {"id": "finance-expense-payroll", "name": "Заработная плата", "kind": "expense", "status": "active"},
        {"id": "finance-expense-rent", "name": "Аренда и коммунальные", "kind": "expense", "status": "active"},
        {"id": "finance-expense-supplies", "name": "Хозяйственные расходы", "kind": "expense", "status": "active"},
        {"id": "finance-expense-marketing", "name": "Маркетинг", "kind": "expense", "status": "active"},
        {"id": "finance-expense-tax", "name": "Налоги и комиссии", "kind": "expense", "status": "active"},
        {"id": "finance-expense-other", "name": "Прочие расходы", "kind": "expense", "status": "active"},
    ]
    finance_accounts = [
        {"id": "finance-bank", "name": "Расчётный счёт", "type": "bank", "branchId": None, "openingBalance": 150000, "status": "active"},
        {"id": "finance-safe", "name": "Сейф", "type": "safe", "branchId": None, "openingBalance": 30000, "status": "active"},
        {"id": f"finance-cash-{branch_id}", "name": f"Касса · {branch['short']}", "type": "cash", "branchId": branch_id, "openingBalance": 10000, "status": "active"},
    ]

    def transaction(number: int, kind: str, amount: float, account: str, category: str | None, days_ago: int, counterparty: str, comment: str, destination: str | None = None) -> dict[str, Any]:
        return {
            "id": f"demo-finance-{number}", "number": f"ФО-{number:04d}", "type": kind,
            "occurredAt": (now - timedelta(days=days_ago)).date().isoformat(), "accountId": account,
            "destinationAccountId": destination, "categoryId": category, "branchId": branch_id,
            "amount": amount, "counterparty": counterparty, "comment": comment,
            "createdAt": _iso(now - timedelta(days=days_ago)), "createdBy": "daison",
        }

    finance_transactions = [
        transaction(7, "expense", 8500, "finance-bank", "finance-expense-supplies", 1, "ХозМаркет", "Расходные материалы и упаковка"),
        transaction(6, "expense", 2400, f"finance-cash-{branch_id}", "finance-expense-other", 3, "Сервис оборудования", "Профилактика кофемашины"),
        transaction(5, "expense", 12000, "finance-bank", "finance-expense-marketing", 6, "Digital Studio", "Реклама и фотосъёмка меню"),
        transaction(4, "expense", 68000, "finance-bank", "finance-expense-payroll", 8, "Команда Buffet 1", "Аванс сотрудникам"),
        transaction(3, "expense", 95000, "finance-bank", "finance-expense-rent", 12, "Арендодатель", "Аренда помещения"),
        transaction(2, "expense", 17600, "finance-bank", "finance-expense-tax", 15, "Банк и налоговая", "Комиссии и обязательные платежи"),
        transaction(1, "income", 15000, "finance-bank", "finance-income-other", 18, "Корпоративный заказ", "Предоплата за обслуживание группы"),
    ]

    stations = [
        {"name": "Горячий цех", "branchId": branch_id, "warehouse": f"Склад · {branch_name}", "destination": "Экран горячего цеха"},
        {"name": "Холодный цех", "branchId": branch_id, "warehouse": f"Склад · {branch_name}", "destination": "Принтер холодного цеха"},
        {"name": "Пекарня", "branchId": branch_id, "warehouse": f"Склад · {branch_name}", "destination": "Экран пекарни"},
        {"name": "Бар", "branchId": branch_id, "warehouse": f"Склад · {branch_name}", "destination": "Без печати"},
    ]

    return {
        "schemaVersion": max(2, int(existing_state.get("schemaVersion", 2))),
        "branches": branches,
        "suppliers": suppliers,
        "ingredients": ingredients,
        "products": products,
        "recipes": recipes,
        "preparations": preparations,
        "menuCategories": menu_categories,
        "ingredientCategories": ingredient_categories,
        "stations": stations,
        "logisticsState": {
            "requests": [], "branchStocks": {branch_id: stocks}, "branchCosts": {branch_id: costs},
            "directOrders": [], "supplies": supplies, "pointTransfers": [], "inventories": inventories,
            "batches": batches, "stockLedger": ledger, "supplyModel": "poster",
        },
        "sales": sales,
        "financeState": {"transactions": finance_transactions, "accounts": finance_accounts, "categories": finance_categories},
    }


def demo_state_summary(state: dict[str, Any]) -> dict[str, int]:
    logistics = state["logisticsState"]
    return {
        "branches": len(state["branches"]),
        "ingredientCategories": len(state["ingredientCategories"]),
        "menuCategories": len(state["menuCategories"]),
        "ingredients": len(state["ingredients"]),
        "products": len(state["products"]),
        "recipes": len(state["recipes"]),
        "preparations": len(state["preparations"]),
        "stations": len(state["stations"]),
        "suppliers": len(state["suppliers"]),
        "receipts": len(logistics.get("supplies", [])),
        "batches": len(logistics["batches"]),
        "sales": len(state["sales"]),
        "financeTransactions": len(state["financeState"]["transactions"]),
    }
