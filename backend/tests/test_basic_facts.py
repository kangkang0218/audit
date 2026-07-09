def test_extracts_required_real_facts(real_facts) -> None:
    facts = {fact.field_name: fact for fact in real_facts}

    assert facts["投标人名称"].value == "中和刚大工程顾问有限公司"
    assert facts["项目负责人"].value == "张军校"
    assert facts["基本费率折扣系数"].value == "0.53"
    assert facts["审减费率折扣系数"].value == "0.53"
    assert facts["保证金声明金额"].value == "10000 元"
    assert facts["投标人名称"].evidence[0].pdf_page == 5


def test_does_not_copy_declaration_into_proof_amount(real_facts) -> None:
    facts = {fact.field_name: fact for fact in real_facts}

    assert facts["是否发现缴款证明"].value is True
    assert facts["缴款证明金额"].value is None
    assert facts["缴款证明金额"].status == "需人工复核"

