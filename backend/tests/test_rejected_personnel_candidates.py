import json


def test_rejected_candidates_are_separate_from_formal_personnel(
    end_to_end_output,
) -> None:
    people = json.loads((end_to_end_output / "personnel.json").read_text())
    rejected = json.loads(
        (end_to_end_output / "rejected_personnel_candidates.json").read_text()
    )
    invalid = {"高级", "中级", "初级", "助理", "一级", "二级", "三级"}

    assert not invalid.intersection(item["name"] for item in people)
    assert all(item["creation_decision"] == "reject" for item in rejected)
    assert all("candidate_value_masked" in item for item in rejected)


def test_personnel_audit_contains_no_unmasked_long_number(
    end_to_end_output,
) -> None:
    text = (end_to_end_output / "personnel_extraction_audit.json").read_text()
    assert "Bearer " not in text
    assert "base64" not in text.lower()
