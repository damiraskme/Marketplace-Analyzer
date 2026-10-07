from decimal import Decimal

from app.common.events import AlertType


def types(alerts) -> list[AlertType]:
    return [alert.alert_type for alert in alerts]


def test_drop_below_own_price_alerts_and_suggests(scenario):
    _, alerts = scenario.change(scenario.competitors["A"], "9500")

    assert types(alerts) == [AlertType.COMPETITOR_PRICE_DROP, AlertType.NEW_SUGGESTION]

    drop, suggestion = alerts
    assert drop.text == (
        "TechnoMart: Wireless Earbuds X1 dropped its price from 11000.00 to 9500.00. "
        "Your price for Wireless Earbuds X1 is 10000.00."
    )
    assert suggestion.suggested_price == Decimal("9490")
    assert suggestion.suggestion_id is not None
    assert suggestion.text == (
        "Suggested price for Wireless Earbuds X1: 9490.00 (now 10000.00). "
        "The cheapest competitor is at 9500.00. This price is 10.00 below it."
    )
    assert scenario.pending_suggestions() == [Decimal("9490")]


def test_drop_that_stays_above_own_price_is_quiet(scenario):
    scenario.change(scenario.competitors["A"], "10500")
    _, alerts = scenario.change(scenario.competitors["B"], "10800")

    assert AlertType.COMPETITOR_PRICE_DROP not in types(alerts)


def test_large_jump_alert(scenario):
    _, alerts = scenario.change(scenario.competitors["A"], "7700")

    assert types(alerts) == [AlertType.LARGE_JUMP, AlertType.NEW_SUGGESTION]
    assert alerts[0].text == (
        "TechnoMart: Wireless Earbuds X1 changed its price by -30.00%, from 11000.00 to 7700.00."
    )


def test_out_of_stock_alert(scenario):
    scenario.change(scenario.competitors["A"], "11000.01")
    _, alerts = scenario.change(scenario.competitors["A"], "11000.01", in_stock=False)

    assert types(alerts) == [AlertType.COMPETITOR_OUT_OF_STOCK]
    assert alerts[0].text == "TechnoMart: Wireless Earbuds X1 is out of stock."


def test_same_suggestion_is_not_repeated(scenario):
    scenario.change(scenario.competitors["A"], "9500")
    _, alerts = scenario.change(scenario.competitors["B"], "9900")

    assert AlertType.NEW_SUGGESTION not in types(alerts)
    assert scenario.pending_suggestions() == [Decimal("9490")]


def test_new_suggestion_replaces_the_pending_one(scenario):
    scenario.change(scenario.competitors["A"], "9500")
    _, alerts = scenario.change(scenario.competitors["B"], "9300")

    assert AlertType.NEW_SUGGESTION in types(alerts)
    assert scenario.pending_suggestions() == [Decimal("9290")]


def test_pending_suggestion_is_dropped_when_own_price_matches(scenario):
    scenario.change(scenario.competitors["A"], "9500")
    _, alerts = scenario.change(scenario.own, "9490")

    assert alerts == []
    assert scenario.pending_suggestions() == []
