from decimal import Decimal


def test_undercuts_cheapest_competitor(scenario):
    scenario.set_competitor("A", "9000")
    scenario.set_competitor("B", "9500")
    scenario.set_competitor("C", "9800")

    assert scenario.suggest_price() == Decimal("8990")


def test_never_goes_below_floor(scenario):
    scenario.set_competitor("A", "6500")

    assert scenario.suggest_price() == Decimal("7000")


def test_margin_wins_when_stricter_than_floor(scenario):
    scenario.set_rules(floor="5000", ceiling="12000", margin="30")
    scenario.set_competitor("A", "7000")

    assert scenario.suggest_price() == Decimal("7800")


def test_no_competitor_in_stock_gives_ceiling(scenario):
    for name in "ABC":
        scenario.set_competitor(name, "9000", in_stock=False)

    assert scenario.suggest_price() == Decimal("12000")


def test_capped_at_ceiling(scenario):
    for name in "ABC":
        scenario.set_competitor(name, "15000")

    assert scenario.suggest_price() == Decimal("12000")


def test_out_of_stock_competitor_is_ignored(scenario):
    scenario.set_competitor("A", "5000", in_stock=False)
    scenario.set_competitor("B", "9000")

    assert scenario.suggest_price() == Decimal("8990")


def test_margin_above_ceiling_still_protects_margin(scenario):
    scenario.set_rules(floor="5000", ceiling="6500", margin="15")
    scenario.set_competitor("A", "6000")

    assert scenario.suggest_price() == Decimal("6900")


def test_product_without_rules_gets_no_suggestion(scenario):
    scenario.cursor.execute("DELETE FROM pricing_rules WHERE product_id = :id", id=scenario.product_id)

    assert scenario.suggest_price() is None
