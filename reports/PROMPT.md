# Agent Prompt — Generate Quality Report

## Reference Documents

**Before writing anything, read these files to calibrate section structure, table formatting, writing style, and level of detail:**

- `reports/cve-1999-0016.md`
- `reports/cve-2024-3400.md`
- `reports/cve-2014-0160.md`

The output for any new CVE must match those documents exactly in section count, section order, heading text, table column names, judgment language (통과 / 실패 / 비일관 / 전 통과 / 전 실패), and writing style. Do not add, remove, or rename any section.

---

## Task

For each CVE ID that has guide files under `guides/{cve_id}/` but does **not** yet have a corresponding `reports/{cve_id}.md`, read all guide files and produce the report.

## Input

- `guides/{cve_id}/{case}_{run}.json` — generated guide files. Each file encodes one run of one context variant. Run numbers are `_1`, `_2`, `_3`. All variants and all runs must be read before writing the report.
- `contexts/{cve_id}/full.json` — for reference when assessing what information was available to the model.
- `analyses/{cve_id}.md` — for reference on expected field contributions and test case intent.

## Discovery Logic

1. List all CVE IDs that have at least one file under `guides/{cve_id}/`.
2. For each CVE ID, check whether `reports/{cve_id}.md` already exists.
3. Process only the CVEs for which the report is missing.

---

## Output — `reports/{cve_id}.md`

Write in Korean. Field names, file paths, JSON key names, and source identifiers stay in their original form.

### Pass / Fail Criterion

A guide **fails** if `metadata.generation_error` is non-empty. A guide **passes** if `metadata.generation_error` is empty or absent. Apply this criterion consistently to every run of every case.

### Section structure (must match existing documents exactly)

```
# {CVE_ID} 가이드 품질 비교 분석

> **생성 일자**: {YYYY-MM-DD}

## TL;DR

Bullet list. Cover:
- The overall pass/fail pattern across all cases and runs (highlight any inconsistencies).
- Which field or data source is the single most decisive contributor to pass/fail.
- Any cross-cutting bugs present in every case and run (e.g. input_tokens: 3).
- Any ghost source attribution pattern.
- Any notable non-deterministic behavior.
- An actionable recommendation (if any).

---

**판정 기준**: `metadata.generation_error`가 비어 있지 않으면 실패.

## 1. 케이스별 결과

Pipe-formatted summary table: | 케이스 | 런 1 | 런 2 | 런 3 | 최종 판정 |
Each cell in 런 N columns: "통과 ({tok} tok)" or "**실패** ({tok} tok)".
최종 판정: "전 통과", "전 실패", or "**비일관** (N/3 통과)" as appropriate.
Bold the 실패 cells. Use backtick-quoted case names.

Then one subsection per case (### `{case}` — {판정}), containing:
- Per-run behavior described concisely. Group runs that behaved identically. Highlight any run that deviated.
- Token counts where informative (especially on anomalous runs).
- Sources used, ghost source citations, reasoning anomalies, content accuracy issues.
- Any **주의** note if the model appears to use pre-training knowledge not derivable from context.

---

## 2. 공통 이슈

One entry per cross-cutting issue found across multiple cases or runs. Each entry has a bold header and 1–3 sentences. Cover:
- Ghost source attribution (which sources, which cases).
- Any token paradox or extreme variance.
- The input_tokens: 3 bug (if present).
- CVE reserved date inconsistency (if applicable).

If token variance data is informative, include a pipe-formatted table: | 케이스 | 런 1 | 런 2 | 런 3 | 범위 |

---

## 3. 런별 일관성 요약

Two tables:

**판정 일관성 table**: | 케이스 | 런 1 | 런 2 | 런 3 | 일관성 |
Values: "통과" / "**실패**" / "일관" / "**비일관**"

**토큰 분산 table** (if variance is notable): | 케이스 | 런 1 | 런 2 | 런 3 | 분산 |
Sort rows by descending variance. Bold the most extreme values.

After the tables, 3–5 bullet observations on what the consistency data reveals: which inconsistencies are non-deterministic (same input, different outcome), which are structural (different input causes different outcome), and any patterns in which run number tends to deviate.

---

## 4. 필드 중요도 결론

Three subsections, each with a pipe-formatted table: | 필드 | 이유 |

### 절대적으로 중요
Fields without which the guide fails or degrades severely across all runs.

### 유용하지만 필수적이지 않음
Fields whose absence causes partial quality degradation but not failure.

### 기여 없음 / 부작용 있음
Fields that are empty, duplicated, or actively harmful (e.g. ghost sources inducing false attribution, erroneous affected_products).
```

---

## Style Rules

- Write in Korean throughout.
- Tables must be pipe-formatted markdown.
- Use `---` horizontal rules between major sections exactly as in the reference documents.
- Bold (`**...**`) failure cells in tables and key terms in TL;DR bullets.
- Keep case subsection descriptions concise — group identical-behavior runs rather than repeating the same observation three times.
- Do not add sections beyond the four defined above, and do not omit any.
