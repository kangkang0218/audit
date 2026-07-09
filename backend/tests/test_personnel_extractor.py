def test_extracts_real_personnel_without_name_allowlist(real_personnel) -> None:
    names = {person.name for person in real_personnel}

    assert {"张军校", "杨敬宇", "杜娟", "盖泰嘉", "李杨"} <= names
    assert {"杨利利", "梅盟盟", "张丹", "程亚苹", "樊建云", "张宝林"} <= names


def test_personnel_materials_are_name_range_linked(real_personnel) -> None:
    manager = next(
        person
        for person in real_personnel
        if person.name == "张军校" and person.role == "项目负责人"
    )
    agent = next(person for person in real_personnel if person.role == "授权代理人")

    assert manager.labor_contract_found is True
    assert manager.social_security_found is True
    assert agent.name == "张宝林"
    assert agent.social_security_found is True
    assert "*" in (manager.social_security_id_masked or "")


def test_title_words_are_never_accepted_as_person_names(
    real_personnel,
) -> None:
    invalid = {
        "高级",
        "中级",
        "助理",
        "一级",
        "二级",
        "工程师",
        "造价工程师",
    }
    assert not invalid.intersection(
        person.name for person in real_personnel
    )


def test_resume_field_labels_are_never_person_names(
    zhongji_personnel_extraction,
) -> None:
    invalid = {"时间", "毕业学校", "毕业院校", "工作经历", "出生年月"}
    assert not invalid.intersection(
        person.name for person in zhongji_personnel_extraction.personnel
    )


def test_duplicate_personnel_tables_do_not_duplicate_strong_identity(
    zhongji_personnel_extraction,
) -> None:
    project_people = [
        person
        for person in zhongji_personnel_extraction.personnel
        if person.role not in {"法定代表人", "授权代理人"}
    ]
    identities = [(person.name, person.role) for person in project_people]

    assert len(project_people) == 11
    assert len(identities) == len(set(identities))


def test_headerless_personnel_continuation_pages_are_included(
    zhongji_personnel_extraction,
) -> None:
    evidence_pages = {
        evidence.pdf_page
        for person in zhongji_personnel_extraction.personnel
        for evidence in person.evidence
    }

    assert {238, 398, 432, 433} <= evidence_pages


def test_real_swapped_name_role_table_is_semantically_corrected(
    zhongxingyu_personnel_extraction,
) -> None:
    project_people = zhongxingyu_personnel_extraction.personnel
    role_words = {
        "项目负责人",
        "土建负责人",
        "安装负责人",
        "其他成员",
    }

    assert len(project_people) == 13
    assert not role_words.intersection(person.name for person in project_people)
    assert {
        "项目负责人",
        "土建负责人",
        "安装负责人",
        "其他成员",
    } <= {person.role for person in project_people}
