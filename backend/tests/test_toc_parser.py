def test_toc_maps_printed_pages_to_pdf_pages(real_toc) -> None:
    entries = {item.section_name: item for item in real_toc}

    assert entries["投标函"].pdf_page == 5
    assert entries["投标保证金"].pdf_page == 19
    assert entries["投标人基本情况表"].pdf_page == 21
    assert entries["项目管理机构组成表"].pdf_page == 122
    assert entries["投标保证金"].source_method == "toc_text"

