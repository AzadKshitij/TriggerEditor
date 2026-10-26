"""Did-you-mean suggestions."""

from trigger_designer.core.errors.suggest import normalise_name, suggest_names


def test_known_column_typos() -> None:
    assert suggest_names("Amnt", ["Amount", "k", "s"]) == ("Amount",)
    assert suggest_names("custmer id", ["Customer Id", "Total"]) == ("Customer Id",)
    assert suggest_names("Totl", ["Total", "Amount"]) == ("Total",)


def test_no_match_returns_empty() -> None:
    assert suggest_names("zz", ["Amount", "k"]) == ()


def test_exact_normalised_match_wins() -> None:
    assert suggest_names("amount ", ["Amount", "Amount_"]) == ("Amount", "Amount_")


def test_limit_and_duplicates() -> None:
    result = suggest_names("amt", ["Amount", "Amount", "Amt", "Amounts"], limit=2)
    assert len(result) <= 2
    assert len(set(result)) == len(result)


def test_normalise_name() -> None:
    assert normalise_name("Customer_Id - Name") == "customeridname"
