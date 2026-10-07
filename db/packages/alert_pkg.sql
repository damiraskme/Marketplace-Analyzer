CREATE OR REPLACE PACKAGE alert_pkg AS

  PROCEDURE evaluate(
    p_listing_id IN  listings.id%TYPE,
    o_alerts     OUT SYS_REFCURSOR
  );

END alert_pkg;
/
CREATE OR REPLACE PACKAGE BODY alert_pkg AS

  PROCEDURE add_alert(
    p_ids           IN OUT NOCOPY sys.odcinumberlist,
    p_seller_id     IN alerts.seller_id%TYPE,
    p_product_id    IN alerts.product_id%TYPE,
    p_listing_id    IN alerts.listing_id%TYPE,
    p_suggestion_id IN alerts.suggestion_id%TYPE,
    p_alert_type    IN alerts.alert_type%TYPE,
    p_message       IN alerts.message%TYPE
  ) IS
    v_id alerts.id%TYPE;
  BEGIN
    INSERT INTO alerts (seller_id, product_id, listing_id, suggestion_id, alert_type, message)
    VALUES (p_seller_id, p_product_id, p_listing_id, p_suggestion_id, p_alert_type, p_message)
    RETURNING id INTO v_id;

    p_ids.EXTEND;
    p_ids(p_ids.COUNT) := v_id;
  END add_alert;

  PROCEDURE dismiss_pending(p_product_id IN products.id%TYPE) IS
  BEGIN
    UPDATE price_suggestions
       SET status = 'DISMISSED',
           resolved_at = SYS_EXTRACT_UTC(SYSTIMESTAMP)
     WHERE product_id = p_product_id
       AND status = 'PENDING';
  END dismiss_pending;

  PROCEDURE refresh_suggestion(
    p_product IN products%ROWTYPE,
    p_ids     IN OUT NOCOPY sys.odcinumberlist
  ) IS
    v_price         NUMBER;
    v_reason        price_suggestions.reason%TYPE;
    v_pending_price price_suggestions.suggested_price%TYPE;
    v_suggestion_id price_suggestions.id%TYPE;
  BEGIN
    pricing_pkg.suggest(p_product.id, v_price, v_reason);
    IF v_price IS NULL THEN
      RETURN;
    END IF;

    IF v_price = p_product.current_price THEN
      dismiss_pending(p_product.id);
      RETURN;
    END IF;

    SELECT MAX(suggested_price)
      INTO v_pending_price
      FROM price_suggestions
     WHERE product_id = p_product.id
       AND status = 'PENDING';

    IF v_pending_price = v_price THEN
      RETURN;
    END IF;

    dismiss_pending(p_product.id);

    INSERT INTO price_suggestions (product_id, suggested_price, current_price, reason)
    VALUES (p_product.id, v_price, p_product.current_price, v_reason)
    RETURNING id INTO v_suggestion_id;

    add_alert(
      p_ids, p_product.seller_id, p_product.id, NULL, v_suggestion_id, 'NEW_SUGGESTION',
      'Suggested price for ' || p_product.title || ': ' || pricing_pkg.format_price(v_price)
        || ' (now ' || pricing_pkg.format_price(p_product.current_price) || '). ' || v_reason
    );
  END refresh_suggestion;

  PROCEDURE check_competitor(
    p_listing IN listings%ROWTYPE,
    p_product IN products%ROWTYPE,
    p_ids     IN OUT NOCOPY sys.odcinumberlist
  ) IS
    v_price         price_history.price%TYPE;
    v_prev_price    price_history.prev_price%TYPE;
    v_change_pct    price_history.change_pct%TYPE;
    v_is_large_jump price_history.is_large_jump%TYPE;
    v_in_stock      price_history.in_stock%TYPE;
    v_prev_in_stock price_history.in_stock%TYPE;
  BEGIN
    BEGIN
      SELECT price, prev_price, change_pct, is_large_jump, in_stock, prev_in_stock
        INTO v_price, v_prev_price, v_change_pct, v_is_large_jump, v_in_stock, v_prev_in_stock
        FROM (
              SELECT h.price, h.prev_price, h.change_pct, h.is_large_jump, h.in_stock,
                     LAG(h.in_stock) OVER (ORDER BY h.observed_at) AS prev_in_stock,
                     ROW_NUMBER() OVER (ORDER BY h.observed_at DESC) AS rn
                FROM price_history h
               WHERE h.listing_id = p_listing.id
             )
       WHERE rn = 1;
    EXCEPTION
      WHEN NO_DATA_FOUND THEN
        RETURN;
    END;

    IF v_in_stock = 0 AND v_prev_in_stock = 1 THEN
      add_alert(
        p_ids, p_product.seller_id, p_product.id, p_listing.id, NULL, 'COMPETITOR_OUT_OF_STOCK',
        p_listing.title || ' is out of stock.'
      );
    END IF;

    IF v_is_large_jump = 1 THEN
      add_alert(
        p_ids, p_product.seller_id, p_product.id, p_listing.id, NULL, 'LARGE_JUMP',
        p_listing.title || ' changed its price by ' || TO_CHAR(v_change_pct, 'FMS999990.00') || '%, from '
          || pricing_pkg.format_price(v_prev_price) || ' to ' || pricing_pkg.format_price(v_price) || '.'
      );
    ELSIF v_in_stock = 1 AND v_price < v_prev_price AND v_price < p_product.current_price THEN
      add_alert(
        p_ids, p_product.seller_id, p_product.id, p_listing.id, NULL, 'COMPETITOR_PRICE_DROP',
        p_listing.title || ' dropped its price from ' || pricing_pkg.format_price(v_prev_price) || ' to '
          || pricing_pkg.format_price(v_price) || '. Your price for ' || p_product.title || ' is '
          || pricing_pkg.format_price(p_product.current_price) || '.'
      );
    END IF;
  END check_competitor;

  PROCEDURE evaluate(
    p_listing_id IN  listings.id%TYPE,
    o_alerts     OUT SYS_REFCURSOR
  ) IS
    v_listing listings%ROWTYPE;
    v_product products%ROWTYPE;
    v_ids     sys.odcinumberlist := sys.odcinumberlist();
  BEGIN
    SELECT * INTO v_listing FROM listings WHERE id = p_listing_id;
    SELECT * INTO v_product FROM products WHERE id = v_listing.product_id;

    IF v_listing.kind = 'COMPETITOR' THEN
      check_competitor(v_listing, v_product, v_ids);
    END IF;

    refresh_suggestion(v_product, v_ids);

    OPEN o_alerts FOR
      SELECT a.id, a.seller_id, a.product_id, a.alert_type, a.message,
             a.suggestion_id, s.suggested_price, a.created_at
        FROM alerts a
        LEFT JOIN price_suggestions s ON s.id = a.suggestion_id
       WHERE a.id IN (SELECT column_value FROM TABLE(v_ids))
       ORDER BY a.id;
  END evaluate;

END alert_pkg;
/
