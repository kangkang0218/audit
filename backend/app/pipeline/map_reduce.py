from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from app.pipeline.llm_agent import DeepSeekAgent
from app.pipeline.splitter import Section

logger = logging.getLogger(__name__)

_CONSISTENCY_PATH = Path(__file__).resolve().parent / "prompts" / "consistency.txt"


def run_map_reduce(
    sections: list[Section],
    agent: DeepSeekAgent,
    concurrency: int = 5,
    source_filename: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    all_facts: list[dict[str, Any]] = []
    all_personnel: list[dict[str, Any]] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(agent.extract, s): s for s in sections}
        for future in as_completed(futures):
            section = futures[future]
            try:
                result = future.result(timeout=300)
                for fact in result.get("facts", []):
                    fact["source_section"] = section.heading
                    all_facts.append(fact)
                for person in result.get("personnel", []):
                    person["source_section"] = section.heading
                    all_personnel.append(person)
            except Exception as exc:
                msg = f"{section.heading}: {exc}"
                logger.error("[map_reduce] section failed: %s", msg, exc_info=True)
                errors.append(msg)

    merged_facts = _merge_facts(all_facts)
    merged_personnel = _merge_personnel(all_personnel)

    findings = _consistency_check(agent, merged_facts, merged_personnel, source_filename)
    return merged_facts, merged_personnel, findings, errors


def _merge_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for f in facts:
        key = f.get("field_name", "")
        groups.setdefault(key, []).append(f)
    merged: list[dict[str, Any]] = []
    for key, items in groups.items():
        best = max(items, key=lambda x: x.get("confidence", 0))
        sources = list(dict.fromkeys(i.get("source_section", "") for i in items if i.get("source_section")))
        best["source_section"] = "; ".join(sources)
        best["all_values"] = list(dict.fromkeys(i.get("value", "") for i in items))
        merged.append(best)
    return merged


def _merge_personnel(personnel: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for p in personnel:
        name = p.get("name", "")
        cert_nums = tuple(sorted(p.get("certificate_numbers", [])))
        key = f"{name}|{cert_nums}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(p)
    return merged


def _consistency_check(
    agent: DeepSeekAgent,
    facts: list[dict[str, Any]],
    personnel: list[dict[str, Any]],
    source_filename: str,
) -> list[dict[str, Any]]:
    try:
        return _llm_consistency_check(agent, facts, personnel, source_filename)
    except Exception as exc:
        logger.error("[consistency] LLM check failed: %s", exc, exc_info=True)
        return _rule_consistency(facts, personnel)


def _llm_consistency_check(
    agent: DeepSeekAgent,
    facts: list[dict[str, Any]],
    personnel: list[dict[str, Any]],
    source_filename: str,
) -> list[dict[str, Any]]:
    if not _CONSISTENCY_PATH.exists():
        return _rule_consistency(facts, personnel)
    prompt = _CONSISTENCY_PATH.read_text(encoding="utf-8")
    data = json.dumps({"facts": facts, "personnel": personnel, "source_file": source_filename}, ensure_ascii=False)
    response = agent.client.chat.completions.create(
        model=agent.model,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt + "\n\n" + data}],
        temperature=0.1,
        max_tokens=4096,
    )
    result = json.loads(response.choices[0].message.content)
    return result.get("findings", [])


def _rule_consistency(
    facts: list[dict[str, Any]],
    personnel: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    fact_map: dict[str, list[dict[str, Any]]] = {}
    for f in facts:
        fact_map.setdefault(f.get("field_name", ""), []).append(f)

    quote_items = fact_map.get("投标报价", [])
    if len(quote_items) > 1:
        vals = [q.get("value", "") for q in quote_items]
        if len(set(vals)) > 1:
            findings.append({
                "title": "报价一致性", "result": "投标报价存在多个不同值，需人工复核",
                "level": "需人工复核", "rule_code": "QUOTE_CONSISTENCY",
                "evidence": [{"excerpt": str(v)} for v in vals],
                "category": "报价", "required_materials": [],
            })

    guarantee_items = fact_map.get("投标保证金金额", []) + fact_map.get("保证金金额", [])
    if len(guarantee_items) > 1:
        vals = [g.get("value", "") for g in guarantee_items]
        if len(set(vals)) > 1:
            findings.append({
                "title": "保证金一致性", "result": "保证金金额存在多个不同值",
                "level": "需人工复核", "rule_code": "GUARANTEE_CONSISTENCY",
                "evidence": [{"excerpt": str(v)} for v in vals],
                "category": "保证金", "required_materials": [],
            })

    if not findings:
        findings.append({
            "title": "单文件内部一致性", "result": "未发现明显异常",
            "level": "未发现明显异常", "rule_code": "SINGLE_FILE_BASELINE",
            "evidence": [], "category": "综合", "required_materials": [],
        })
    return findings
