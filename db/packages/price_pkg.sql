CREATE OR REPLACE PACKAGE price_pkg AS

  c_unknown_listing CONSTANT PLS_INTEGER := -20001;

  PROCEDURE record_change(
    p_listing_id  IN  listings.id%TYPE,
    p_price       IN  NUMBER,
    p_in_stock    IN  NUMBER,
    p_observed_at IN  TIMESTAMP,
    o_recorded    OUT NUMBER,
    o_change_pct  OUT NUMBER,
    o_is_jump     OUT NUMBER
  );

END price_pkg;
/
CREATE OR REPLACE PACKAGE BODY price_pkg AS

  PROCEDURE record_change(
    p_listing_id  IN  listings.id%TYPE,
    p_price       IN  NUMBER,
    p_in_stock    IN  NUMBER,
    p_observed_at IN  TIMESTAMP,
    o_recorded    OUT NUMBER,
    o_change_pct  OUT NUMBER,
    o_is_jump     OUT NUMBER
  ) IS
    v_listing   listings%ROWTYPE;
    v_threshold pricing_rules.jump_threshold_pct%TYPE;
  BEGIN
    o_recorded := 0;
    o_change_pct := NULL;
    o_is_jump := 0;

    BEGIN
      SELECT * INTO v_listing FROM listings WHERE id = p_listing_id FOR UPDATE;
    EXCEPTION
      WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(c_unknown_listing, 'Listing ' || p_listing_id || ' does not exist');
    END;

    IF v_listing.last_observed_at IS NOT NULL AND p_observed_at <= v_listing.last_observed_at THEN
      RETURN;
    END IF;

    IF v_listing.last_price = p_price AND v_listing.in_stock = p_in_stock THEN
      RETURN;
    END IF;

    IF v_listing.last_price > 0 THEN
      o_change_pct := ROUND((p_price - v_listing.last_price) / v_listing.last_price * 100, 2);

      SELECT MAX(jump_threshold_pct)
        INTO v_threshold
        FROM pricing_rules
       WHERE product_id = v_listing.product_id;

      IF ABS(o_change_pct) >= v_threshold THEN
        o_is_jump := 1;
      END IF;
    END IF;

    INSERT INTO price_history (listing_id, price, in_stock, prev_price, change_pct, is_large_jump, observed_at)
    VALUES (p_listing_id, p_price, p_in_stock, v_listing.last_price, o_change_pct, o_is_jump, p_observed_at);

    UPDATE listings
       SET last_price = p_price,
           in_stock = p_in_stock,
           last_observed_at = p_observed_at
     WHERE id = p_listing_id;

    IF v_listing.kind = 'OWN' THEN
      UPDATE products SET current_price = p_price WHERE id = v_listing.product_id;
    END IF;

    o_recorded := 1;
  END record_change;

END price_pkg;
/
