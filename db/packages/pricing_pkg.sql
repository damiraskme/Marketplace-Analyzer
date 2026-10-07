CREATE OR REPLACE PACKAGE pricing_pkg AS

  FUNCTION format_price(p_amount IN NUMBER) RETURN VARCHAR2;

  PROCEDURE suggest(
    p_product_id IN  products.id%TYPE,
    o_price      OUT NUMBER,
    o_reason     OUT VARCHAR2
  );

  FUNCTION suggest_price(p_product_id IN products.id%TYPE) RETURN NUMBER;

END pricing_pkg;
/
CREATE OR REPLACE PACKAGE BODY pricing_pkg AS

  FUNCTION format_price(p_amount IN NUMBER) RETURN VARCHAR2 IS
  BEGIN
    RETURN TO_CHAR(p_amount, 'FM999999990.00');
  END format_price;

  PROCEDURE suggest(
    p_product_id IN  products.id%TYPE,
    o_price      OUT NUMBER,
    o_reason     OUT VARCHAR2
  ) IS
    v_rule     pricing_rules%ROWTYPE;
    v_cost     products.cost_price%TYPE;
    v_cheapest listings.last_price%TYPE;
    v_lower    NUMBER;
    v_upper    NUMBER;
    v_target   NUMBER;
  BEGIN
    o_price := NULL;
    o_reason := NULL;

    BEGIN
      SELECT * INTO v_rule FROM pricing_rules WHERE product_id = p_product_id;
    EXCEPTION
      WHEN NO_DATA_FOUND THEN
        RETURN;
    END;

    SELECT cost_price INTO v_cost FROM products WHERE id = p_product_id;

    SELECT MIN(last_price)
      INTO v_cheapest
      FROM listings
     WHERE product_id = p_product_id
       AND kind = 'COMPETITOR'
       AND active = 1
       AND in_stock = 1;

    v_lower := GREATEST(v_rule.price_floor, ROUND(v_cost * (1 + v_rule.min_margin_pct / 100), 2));
    v_upper := GREATEST(v_rule.price_ceiling, v_lower);

    IF v_cheapest IS NULL THEN
      o_price := v_upper;
      o_reason := 'No competitor is in stock, so the price can go up to your ceiling.';
      RETURN;
    END IF;

    v_target := v_cheapest - v_rule.undercut_step;

    IF v_target < v_lower THEN
      o_price := v_lower;
      o_reason := 'The cheapest competitor is at ' || format_price(v_cheapest)
        || '. Going lower would break your price floor or minimum margin.';
    ELSIF v_target > v_upper THEN
      o_price := v_upper;
      o_reason := 'The cheapest competitor is at ' || format_price(v_cheapest)
        || ', which is above your price ceiling.';
    ELSE
      o_price := v_target;
      o_reason := 'The cheapest competitor is at ' || format_price(v_cheapest)
        || '. This price is ' || format_price(v_rule.undercut_step) || ' below it.';
    END IF;
  END suggest;

  FUNCTION suggest_price(p_product_id IN products.id%TYPE) RETURN NUMBER IS
    v_price  NUMBER;
    v_reason VARCHAR2(500);
  BEGIN
    suggest(p_product_id, v_price, v_reason);
    RETURN v_price;
  END suggest_price;

END pricing_pkg;
/
