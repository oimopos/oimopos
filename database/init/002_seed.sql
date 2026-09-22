BEGIN;

INSERT INTO branches (name, city, address) VALUES
  ('Центр', 'Бишкек', 'ул. Киевская'),
  ('Азия Молл', 'Бишкек', 'пр. Чынгыза Айтматова, 3'),
  ('Дордой', 'Бишкек', 'рынок Дордой');

INSERT INTO categories (name, sort_order) VALUES
  ('Первые', 10),
  ('Горячее', 20),
  ('Гарниры', 30),
  ('Салаты', 40),
  ('Выпечка', 50),
  ('Напитки', 60);

INSERT INTO products (id, name, category_id, unit, price) VALUES
  (101, 'Шорпо с говядиной', (SELECT id FROM categories WHERE name = 'Первые'), 'порция', 210),
  (102, 'Суп с фрикадельками', (SELECT id FROM categories WHERE name = 'Первые'), 'порция', 180),
  (103, 'Борщ со сметаной', (SELECT id FROM categories WHERE name = 'Первые'), 'порция', 175),
  (104, 'Мампар', (SELECT id FROM categories WHERE name = 'Первые'), 'порция', 190),
  (201, 'Плов праздничный', (SELECT id FROM categories WHERE name = 'Горячее'), 'порция', 230),
  (202, 'Манты с мясом', (SELECT id FROM categories WHERE name = 'Горячее'), 'штука', 55),
  (203, 'Лагман', (SELECT id FROM categories WHERE name = 'Горячее'), 'порция', 250),
  (204, 'Котлета домашняя', (SELECT id FROM categories WHERE name = 'Горячее'), 'штука', 120),
  (205, 'Курица запечённая', (SELECT id FROM categories WHERE name = 'Горячее'), 'порция', 180),
  (301, 'Картофельное пюре', (SELECT id FROM categories WHERE name = 'Гарниры'), 'порция', 75),
  (302, 'Гречка', (SELECT id FROM categories WHERE name = 'Гарниры'), 'порция', 70),
  (303, 'Рис отварной', (SELECT id FROM categories WHERE name = 'Гарниры'), 'порция', 65),
  (401, 'Салат Ачичук', (SELECT id FROM categories WHERE name = 'Салаты'), 'порция', 85),
  (402, 'Салат свежий', (SELECT id FROM categories WHERE name = 'Салаты'), 'порция', 80),
  (403, 'Винегрет', (SELECT id FROM categories WHERE name = 'Салаты'), 'порция', 75),
  (501, 'Самса с мясом', (SELECT id FROM categories WHERE name = 'Выпечка'), 'штука', 75),
  (502, 'Лепёшка', (SELECT id FROM categories WHERE name = 'Выпечка'), 'штука', 35),
  (503, 'Боорсок', (SELECT id FROM categories WHERE name = 'Выпечка'), 'порция', 60),
  (601, 'Чай чёрный', (SELECT id FROM categories WHERE name = 'Напитки'), 'чайник', 30),
  (602, 'Компот', (SELECT id FROM categories WHERE name = 'Напитки'), 'стакан', 45),
  (603, 'Айран', (SELECT id FROM categories WHERE name = 'Напитки'), 'стакан', 55),
  (604, 'Вода 0,5 л', (SELECT id FROM categories WHERE name = 'Напитки'), 'бутылка', 40);

INSERT INTO ingredients (id, name, category, unit, stock, average_cost, stock_limit) VALUES
  ('rice', 'Рис лазер', 'Крупы', 'кг', 68, 96, 25),
  ('beef', 'Говядина', 'Мясо', 'кг', 32, 520, 20),
  ('carrot', 'Морковь', 'Овощи', 'кг', 25, 55, 10),
  ('onion', 'Лук репчатый', 'Овощи', 'кг', 18, 45, 10),
  ('oil', 'Масло растительное', 'Бакалея', 'л', 12, 145, 10),
  ('salt', 'Соль', 'Бакалея', 'кг', 8, 30, 3),
  ('spices', 'Специи для плова', 'Бакалея', 'кг', 2, 760, 1),
  ('potato', 'Картофель', 'Овощи', 'кг', 52, 48, 20),
  ('flour', 'Мука высший сорт', 'Бакалея', 'кг', 76, 54, 25),
  ('chicken', 'Курица', 'Мясо', 'кг', 24, 260, 15),
  ('tomato', 'Помидоры', 'Овощи', 'кг', 15, 130, 8),
  ('tea', 'Чай чёрный', 'Напитки', 'кг', 1.2, 680, 1.5);

INSERT INTO recipes (product_id, yield_grams, station) VALUES
  (201, 380, 'Кухня'),
  (203, 450, 'Кухня'),
  (101, 420, 'Кухня'),
  (205, 210, 'Кухня'),
  (401, 160, 'Холодный цех');

INSERT INTO recipe_items (product_id, ingredient_id, gross_amount, net_amount, measure) VALUES
  (201, 'rice', 150, 150, 'г'), (201, 'beef', 115, 100, 'г'),
  (201, 'carrot', 82, 70, 'г'), (201, 'onion', 35, 30, 'г'),
  (201, 'oil', 25, 25, 'мл'), (201, 'salt', 3, 3, 'г'), (201, 'spices', 2, 2, 'г'),
  (203, 'beef', 130, 110, 'г'), (203, 'flour', 150, 150, 'г'),
  (203, 'onion', 45, 40, 'г'), (203, 'tomato', 90, 80, 'г'),
  (203, 'oil', 18, 18, 'мл'), (203, 'spices', 2, 2, 'г'),
  (101, 'beef', 120, 100, 'г'), (101, 'potato', 150, 125, 'г'),
  (101, 'carrot', 35, 30, 'г'), (101, 'onion', 30, 26, 'г'),
  (101, 'salt', 3, 3, 'г'), (101, 'spices', 1, 1, 'г'),
  (205, 'chicken', 260, 200, 'г'), (205, 'oil', 7, 7, 'мл'),
  (205, 'salt', 3, 3, 'г'), (205, 'spices', 2, 2, 'г'),
  (401, 'tomato', 130, 120, 'г'), (401, 'onion', 45, 38, 'г'), (401, 'salt', 2, 2, 'г');

COMMIT;

