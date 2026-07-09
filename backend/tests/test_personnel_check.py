from app.validators.single_file import SINGLE_FILE_BOUNDARIES, boundary_findings, check_personnel


def test_project_manager_is_in_team(real_facts, real_personnel) -> None:
    findings = check_personnel(real_facts, real_personnel)
    manager = next(item for item in findings if item.rule_code.endswith("MANAGER_IN_TEAM.v1"))

    assert manager.result == "未发现明显矛盾"


def test_boundaries_are_fixed_text() -> None:
    assert [item.result for item in boundary_findings()] == SINGLE_FILE_BOUNDARIES

