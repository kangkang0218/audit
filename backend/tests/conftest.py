import os
from pathlib import Path

import pytest

os.environ.setdefault("BID_REVIEW_ENVIRONMENT", "test")
os.environ.setdefault("BID_REVIEW_DATABASE_URL", "sqlite+pysqlite:///:memory:")


@pytest.fixture(scope="session")
def real_pdf_path() -> Path:
    path = Path(__file__).parents[2] / "samples" / "中和刚大工程顾问有限公司(1)(1).pdf"
    assert path.is_file()
    return path


@pytest.fixture(scope="session")
def zhongji_pdf_path() -> Path:
    path = Path(__file__).parents[2] / "zzsj619" / "中和中基工程管理有限公司.pdf"
    assert path.is_file()
    return path


@pytest.fixture(scope="session")
def zhongji_personnel_extraction(zhongji_pdf_path: Path):
    from app.extractors.personnel import extract_personnel_with_audit
    from app.parsers.pdf_parser import parse_pdf

    return extract_personnel_with_audit(parse_pdf(zhongji_pdf_path), [])


@pytest.fixture(scope="session")
def zhongxingyu_pdf_path() -> Path:
    path = Path(__file__).parents[2] / "zzsj619" / "中兴豫建设管理有限公司(1).pdf"
    assert path.is_file()
    return path


@pytest.fixture(scope="session")
def zhongxingyu_personnel_extraction(zhongxingyu_pdf_path: Path):
    from app.extractors.personnel import extract_personnel_with_audit
    from app.parsers.pdf_parser import parse_pdf

    return extract_personnel_with_audit(parse_pdf(zhongxingyu_pdf_path), [])


@pytest.fixture(scope="session")
def parsed_real(real_pdf_path: Path):
    from app.parsers.pdf_parser import parse_pdf

    return parse_pdf(real_pdf_path)


@pytest.fixture(scope="session")
def real_toc(parsed_real):
    from app.parsers.toc_parser import parse_toc

    return parse_toc(parsed_real)


@pytest.fixture(scope="session")
def real_facts(parsed_real, real_toc):
    from app.extractors.basic_facts import extract_basic_facts

    return extract_basic_facts(parsed_real, real_toc)


@pytest.fixture(scope="session")
def real_personnel(parsed_real, real_facts):
    from app.extractors.personnel import extract_personnel

    return extract_personnel(parsed_real, real_facts)


@pytest.fixture(scope="session")
def end_to_end_output(tmp_path_factory: pytest.TempPathFactory, real_pdf_path: Path) -> Path:
    from app.core.config import Settings
    from app.services.single_file_review import run_review

    output = tmp_path_factory.mktemp("end-to-end")
    run_review(
        real_pdf_path,
        output,
        Settings(
            _env_file=None,
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            enable_llm=False,
            enable_ocr=False,
        ),
    )
    return output
