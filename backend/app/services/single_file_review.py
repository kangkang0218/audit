from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, AsyncGenerator

from app.core.config import Settings
from app.excel.renderer import render_review_workbook
from app.pipeline import DeepSeekAgent, run_ocr, run_map_reduce, split_markdown
from app.pipeline.discriminator import PdfClass, classify_pdf


async def run_review_stream(
    input_path: Path,
    output_dir: Path,
    settings: Settings,
) -> AsyncGenerator[str, None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_start = time.monotonic()
    _emit = lambda d: json.dumps({"ts": time.monotonic() - total_start, **d}, ensure_ascii=False)

    yield _emit({"stage": "classify", "label": "PDF 类型判别", "status": "active"})
    t0 = time.monotonic()
    classification = classify_pdf(input_path)
    yield _emit({"stage": "classify", "label": "PDF 类型判别", "status": "done",
                 "elapsed": round(time.monotonic() - t0, 2),
                 "pdf_class": classification.pdf_class.name,
                 "text_pages": classification.text_pages,
                 "scanned_pages": classification.scanned_pages})

    if classification.pdf_class == PdfClass.TEXT:
        result_md = classification.markdown
        ocr_page_texts: dict[int, str] = {}
        yield _emit({"stage": "ocr", "label": "PyMuPDF 直读 (跳过 OCR)", "status": "done",
                     "elapsed": 0.0, "pages": classification.total_pages})
    else:
        backend_label = "MinerU hybrid-engine"
        total_ocr_pages = classification.total_pages
        yield _emit({"stage": "ocr", "label": backend_label, "status": "active",
                     "total_pages": total_ocr_pages})
        t0 = time.monotonic()

        import asyncio as _asyncio
        from concurrent.futures import ThreadPoolExecutor
        loop = _asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_ocr, input_path)
            while not future.done():
                await _asyncio.sleep(1.5)
                elapsed = time.monotonic() - t0
                est_total = max(total_ocr_pages * 0.35, 10)
                pct = 5 + min(int(elapsed / est_total * 30), 30)
                yield _emit({"stage": "ocr", "label": backend_label, "status": "running",
                             "progress": pct, "total_pages": total_ocr_pages, "elapsed_partial": round(elapsed, 1)})
            ocr_result = future.result()
        result_md = ocr_result.markdown
        ocr_page_texts = ocr_result.page_texts

        # Save extracted images
        if ocr_result.images:
            img_dir = output_dir / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            for idx, img in enumerate(ocr_result.images):
                try:
                    data = img.get("data")
                    if data and isinstance(data, bytes):
                        fname = img.get("filename") or f"page{img.get('page',0)}_img{idx}.png"
                        (img_dir / fname).write_bytes(data)
                except Exception:
                    pass

        yield _emit({"stage": "ocr", "label": backend_label, "status": "done",
                     "elapsed": round(time.monotonic() - t0, 1), "pages": total_ocr_pages,
                     "page_texts_count": len(ocr_page_texts)})

    yield _emit({"stage": "split", "label": "Markdown 分片", "status": "active"})
    t0 = time.monotonic()
    if ocr_page_texts:
        sections = _sections_from_pages(ocr_page_texts)
    else:
        sections = split_markdown(result_md)
    yield _emit({"stage": "split", "label": "Markdown 分片", "status": "done",
                 "elapsed": round(time.monotonic() - t0, 2), "sections": len(sections)})

    yield _emit({"stage": "llm", "label": "LLM 并行提取", "status": "active", "total": len(sections)})
    t0 = time.monotonic()
    agent = DeepSeekAgent(
        api_key=settings.deepseek_api_key or "",
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    facts, personnel, findings, llm_errors, tables = [], [], [], [], []
    for event in run_map_reduce(
        sections, agent,
        concurrency=settings.map_reduce_concurrency,
        source_filename=input_path.name,
    ):
        if event.get("status") == "running":
            yield _emit({"stage": "llm", "label": "LLM 并行提取", "status": "running",
                         "progress": event.get("progress", 42),
                         "completed": event.get("completed", 0), "total": event.get("total", len(sections))})
        elif event.get("status") == "done":
            facts = event.get("facts_result", [])
            personnel = event.get("personnel_result", [])
            findings = event.get("findings_result", [])
            tables = event.get("tables_result", [])
            llm_errors = event.get("errors", [])
            yield _emit({"stage": "llm", "label": "LLM 并行提取", "status": "done",
                         "elapsed": round(time.monotonic() - t0, 1),
                         "facts": event.get("facts", 0), "personnel": event.get("personnel", 0),
                         "total_sections": len(sections), "errors": llm_errors,
                         "tables": len(tables)})

    yield _emit({"stage": "consistency", "label": "一致性校验", "status": "active"})
    t0 = time.monotonic()
    yield _emit({"stage": "consistency", "label": "一致性校验", "status": "done",
                 "elapsed": round(time.monotonic() - t0, 1), "findings": len(findings)})

    yield _emit({"stage": "excel", "label": "生成 Excel", "status": "active"})
    t0 = time.monotonic()
    review = _build_review(input_path.name, facts, personnel, findings, tables)
    bidder = _safe_bidder(facts, input_path)
    excel_path = output_dir / f"{bidder}投标文件三项审查_提取与判断建议.xlsx"
    render_review_workbook(review, excel_path)
    yield _emit({"stage": "excel", "label": "生成 Excel", "status": "done",
                 "elapsed": round(time.monotonic() - t0, 1)})

    total_elapsed = round(time.monotonic() - total_start, 1)
    yield _emit({"stage": "done", "label": "完成", "total_elapsed": total_elapsed,
                 "filename": excel_path.name, "result_path": str(excel_path)})


def _safe_bidder(facts: list[dict[str, Any]], input_path: Path) -> str:
    bidder = next(
        (str(f.get("value", "")) for f in facts if f.get("field_name") == "投标人名称" and f.get("value")),
        re.sub(r"\(\d+\)$", "", input_path.stem),
    )
    return re.sub(r'[\\/:*?"<>|]', "_", bidder)


def _build_review(
    source_file: str,
    facts: list[dict[str, Any]],
    personnel: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    tables: list[dict[str, Any]] | None = None,
) -> Any:
    from app.schemas.phase_a import EvidenceItem
    from app.schemas.review import ReviewWorkbook

    _CATEGORIES = {
        "项目名称": "基础信息", "招标人名称": "基础信息", "投标人名称": "基础信息", "投标文件日期": "基础信息",
        "投标报价": "报价", "投标函报价": "报价", "投标函附录报价": "报价",
        "基本费率折扣系数": "报价", "审减费率折扣系数": "报价", "增值税税率": "报价",
        "投标有效期": "响应信息", "服务期限": "响应信息",
        "项目负责人": "人员", "项目负责人注册编号": "人员", "项目负责人专业": "人员",
        "保证金声明金额": "保证金", "是否发现缴款证明": "保证金", "是否发现电子保函": "保证金",
        "是否发现基本账户材料": "保证金", "缴款证明金额": "保证金", "电子保函金额": "保证金",
        "保证金形式": "保证金",
        "法定代表人": "主体信息", "授权代理人": "主体信息", "统一社会信用代码": "主体信息",
        "注册地址": "主体信息", "开户银行": "主体信息", "银行账号": "主体信息",
    }

    fact_rows: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for fact in facts:
        fname = fact.get("field_name", "")
        fvalue = fact.get("value", "")
        excerpt = fact.get("source_excerpt", "")
        section = fact.get("source_section", "")
        conf = fact.get("confidence", 0.0)
        cat = _CATEGORIES.get(fname, "通用")
        status = "已提取" if conf >= 0.5 else "需复核"
        fact_rows.append({
            "问题编号": "N/A", "问题分类": cat, "提取项": fname,
            "提取结果": str(fvalue) if fvalue else "无法确认",
            "是否提取成功": "是" if status == "已提取" else "否",
            "信息归属判断": "当前投标文件内容", "文件名": source_file,
            "PDF实际页码": "/", "文件内印刷页码": "/",
            "自动行号/页面区域": section or "/",
            "原文摘录": excerpt or "/",
            "置信度": "高" if conf >= 0.85 else ("中/需复核" if conf >= 0.5 else "低"),
            "分析/备注": fact.get("note", ""),
        })
    for fact in facts:
        conf = fact.get("confidence", 0.0)
        if conf < 0.5:
            unavailable.append({
                "问题编号": "通用", "提取项/判断项": fact.get("field_name", ""),
                "是否属于当前投标文件内容": "是",
                "无法提取/无法判断原因": f"置信度 {conf}，需人工复核",
                "缺少文件或需补充材料": "高清原件或人工复核",
                "当前文件具体位置": fact.get("source_section", "/"),
                "是否红色标注": "是", "复核建议": "核对原始 PDF 图像页或补充材料。",
            })
    finding_rows: list[dict[str, Any]] = []
    for finding in findings:
        evidence_list = finding.get("evidence", [])
        excerpts = "; ".join(str(e.get("excerpt", "")) for e in evidence_list) or "/"
        finding_rows.append({
            "问题编号": "N/A", "判断事项": finding.get("title", ""),
            "涉及提取项": finding.get("category", "综合"),
            "当前证据摘要": excerpts,
            "判断依据范围": finding.get("rule_code", ""),
            "初步判断": finding.get("result", ""),
            "判断等级": finding.get("level", "未发现明显异常"),
            "是否需要补充材料": "是" if finding.get("required_materials") else "否",
            "补充材料清单": "; ".join(finding.get("required_materials", [])) or "/",
            "复核建议": "建议人工复核。" if finding.get("level") != "未发现明显异常" else "保留证据。",
        })
    personnel_rows: list[dict[str, Any]] = []
    for person in personnel:
        personnel_rows.append({
            "来源表": "LLM 提取", "姓名": person.get("name", "/"),
            "拟任职务/角色": person.get("role", "/"),
            "职称": person.get("title") or "/",
            "证书名称": person.get("certificate_name") or "/",
            "级别": person.get("certificate_level") or "/",
            "证号": " / ".join(person.get("certificate_numbers", [])) or "/",
            "专业": person.get("specialty") or "/",
            "社保状态": (
                "已发现可关联材料" if person.get("labor_contract_found") or person.get("social_security_id_masked")
                else "未发现或无法关联"
            ),
            "文件名": source_file, "PDF实际页码": "/", "文件内印刷页码": "/",
            "自动行号/页面区域": person.get("source_section", "/"),
            "备注": f"劳动合同: {'已发现' if person.get('labor_contract_found') else '未发现'}"
                    f"; 社保: {'已发现' if person.get('social_security_id_masked') else '未发现'}",
        })

    table_rows: list[dict[str, Any]] = []
    if tables:
        for t in tables:
            table_rows.append({
                "表格类型": t.get("table_type", "unknown"),
                "行数": t.get("row_count", 0),
                "列数": t.get("col_count", 0),
                "预览": t.get("preview", "/"),
                "置信度": t.get("confidence", 0.0),
                "所在章节": t.get("source_section", "/"),
                "处理建议": t.get("note", "/"),
            })

    bidder = next(
        (str(f.get("value", "")) for f in facts if f.get("field_name") == "投标人名称" and f.get("value")),
        "无法确认",
    )
    return ReviewWorkbook(
        source_file=source_file,
        generated_at=datetime.now(UTC).isoformat(),
        overview=[
            {"项目": "源文件", "内容": source_file, "标注状态": "已解析", "备注": ""},
            {"项目": "投标人", "内容": bidder, "标注状态": "已提取", "备注": ""},
            {"项目": "基础事实", "内容": f"{len(facts)} 项", "标注状态": "已完成", "备注": "LLM 提取"},
            {"项目": "人员记录", "内容": f"{len(personnel)} 条", "标注状态": "已完成", "备注": "LLM 提取"},
            {"项目": "规则发现", "内容": f"{len(findings)} 条", "标注状态": "需人工复核", "备注": "不作法律定性"},
        ],
        facts=fact_rows, unavailable=unavailable, findings=finding_rows,
        personnel=personnel_rows,
        bases=[{
            "依据名称": "LLM 单文件内部一致性审查",
            "条款/规则点": "报价、保证金、人员、证书内部一致性",
            "适用问题": "通用", "判断逻辑": "由 DeepSeek V4 Pro 执行交叉验证。",
            "是否需要外部文件": "部分", "官方来源URL": "", "备注": "LLM 驱动审查",
        }],
        required_materials=[],
    )


def _sections_from_pages(page_texts: dict[int, str]) -> list:
    from app.pipeline.splitter import Section
    pages = sorted(page_texts.keys())
    if not pages:
        return [Section(heading="全文", content="", start_page=None, end_page=None)]
    PAGES_PER_CHUNK = 3
    sections = []
    i = 0
    while i < len(pages):
        chunk_pages = pages[i:i + PAGES_PER_CHUNK]
        start_pg = chunk_pages[0]
        end_pg = chunk_pages[-1]
        content = "\n".join(f"<!-- page {p} -->\n{page_texts[p]}" for p in chunk_pages)
        heading = f"第{start_pg}-{end_pg}页" if len(chunk_pages) > 1 else f"第{start_pg}页"
        sections.append(Section(heading=heading, content=content, start_page=start_pg, end_page=end_pg))
        i += PAGES_PER_CHUNK
    return sections
