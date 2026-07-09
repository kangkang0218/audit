from app.schemas.phase_a import ExtractedFactItem
from app.validators.single_file import check_quotes


def quote_fact(name: str, value: str | None) -> ExtractedFactItem:
    return ExtractedFactItem(
        category="报价",
        field_name=name,
        value=value,
        status="已提取" if value is not None else "无法确认",
    )


def test_quote_consistency() -> None:
    finding = check_quotes(
        [
            quote_fact("投标函报价", "0.53"),
            quote_fact("投标函附录报价", "0.53"),
            quote_fact("基本费率折扣系数", "0.53"),
            quote_fact("审减费率折扣系数", "0.53"),
        ]
    )

    assert finding.result == "未发现明显矛盾"


def test_quote_conflict_requires_review() -> None:
    finding = check_quotes(
        [
            quote_fact("投标函报价", "0.53"),
            quote_fact("投标函附录报价", "0.54"),
            quote_fact("基本费率折扣系数", "0.53"),
            quote_fact("审减费率折扣系数", "0.53"),
        ]
    )

    assert finding.result == "存在疑点，需人工复核"

