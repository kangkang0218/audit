from app.validators.single_file import check_guarantee


def test_image_proof_without_amount_requires_review(real_facts) -> None:
    finding = check_guarantee(real_facts)

    assert finding.result == "保证金材料已发现，但金额/日期需人工复核"
    assert finding.level == "需人工复核"

