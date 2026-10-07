INSERT INTO sellers (name, email) VALUES ('Demo Seller', 'demo@example.com')
/
INSERT INTO products (seller_id, sku, title, cost_price, current_price)
SELECT s.id, p.sku, p.title, p.cost_price, p.current_price
  FROM sellers s
 CROSS JOIN (
        SELECT 'OWN-1001' AS sku, 'Wireless Earbuds X1' AS title, 6000 AS cost_price, 9990 AS current_price FROM dual
        UNION ALL
        SELECT 'OWN-1002', 'Slim Phone Case', 900, 1990 FROM dual
        UNION ALL
        SELECT 'OWN-1003', 'USB-C Cable 2 m', 500, 1490 FROM dual
       ) p
 WHERE s.email = 'demo@example.com'
/
INSERT INTO listings (product_id, kind, marketplace, sku, title)
SELECT id, 'OWN', 'fake', sku, title
  FROM products
/
INSERT INTO listings (product_id, kind, marketplace, sku, title)
SELECT p.id, 'COMPETITOR', 'fake', REPLACE(p.sku, 'OWN', 'COMP') || '-' || c.suffix, c.shop || ': ' || p.title
  FROM products p
 CROSS JOIN (
        SELECT 'A' AS suffix, 'TechnoMart' AS shop FROM dual
        UNION ALL
        SELECT 'B', 'GadgetHub' FROM dual
        UNION ALL
        SELECT 'C', 'SmartStore' FROM dual
       ) c
/
INSERT INTO pricing_rules (product_id, min_margin_pct, price_floor, price_ceiling, undercut_step, jump_threshold_pct)
SELECT id, 15, ROUND(cost_price * 1.2, 2), ROUND(current_price * 1.3, 2), 10, 20
  FROM products
/
