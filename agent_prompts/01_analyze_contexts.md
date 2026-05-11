# Agent Prompt — Generate Context Analysis

## Reference Documents

**Before writing anything, read these files to calibrate structure, tone, depth, and table formatting:**

- `analyses/cve-1999-0016.md`
- `analyses/cve-2024-3400.md`
- `analyses/cve-2014-0160.md`

The output for any new CVE must match those documents exactly in section count, section order, heading text, table column names, and writing style. Do not add, remove, or rename any section.

---

## Task

Scan `contexts/` for CVE IDs. For each CVE ID that does **not** yet have a corresponding `analyses/{cve_id}.md`, read `contexts/{cve_id}/full.json` and produce the analysis document at `analyses/{cve_id}.md`.

## Input

- `contexts/{cve_id}/full.json` — the complete context JSON for that CVE.

## Discovery Logic

1. List all subdirectory names under `contexts/` — each is a CVE ID (e.g. `cve-2024-3400`).
2. For each CVE ID, check whether `analyses/{cve_id}.md` already exists.
3. Process only the CVEs for which that file is missing.

---

## Output — `analyses/{cve_id}.md`

Write in Korean. Field names, file paths, and JSON key names stay in their original form.

### Section structure (must match existing documents exactly)

```
# {CVE_ID} — 컨텍스트 분석

> **생성 일자**: {YYYY-MM-DD}

{One-line CVE summary: attack type, CVSS version + score + severity, KEV status, EPSS score + percentile. Not a heading — sits at the top as a plain paragraph.}

## 1. 생성 전 항상 제거되는 필드 (메인 파이프라인 — `main.py`)

{Explain that the pipeline removes/truncates the fields listed below before passing the context to the model, regardless of what the context JSON contains. Then assess whether each removal is relevant to this specific CVE (i.e. does the field actually exist and contain data).}

The hard-coded pipeline transformations are:
- `threat_intel.epss["time-series"]` — deleted entirely if present.
- `weakness_chain.capecs` — capped to first 5 items if more than 5 exist.
- `weakness_chain.cwes[*].mitigations` — truncated to 500 characters.
- `weakness_chain.capecs[*].execution_flow`, `.mitigations`, `.prerequisites` — truncated to 500 characters.

End with the line "이 CVE에 대한 실질적 영향:" followed by a summary of which removals matter for this CVE. Write "해당 없음" for any that do not apply.

## 2. 현재 제거되지 않는 중복/저신호 필드

Pipe-formatted table with columns: | 필드 | 이유 |

List every field in full.json that is: empty, null, a known-useless value (e.g. "n/a"), purely internal metadata, a duplicate of information already present in another field, or a ghost source in data_sources with no corresponding data block.

## 3. 유용한 필드 및 기여 섹션

Pipe-formatted table with columns: | 필드 | 가이드 섹션 |

List every field that carries actionable information for guide generation. Name the guide section(s) it feeds (e.g. overview, impact_check, decision_guidance, timeline, recommended_actions).

After the table, add one or more bold-header constraint blocks (e.g. **주요 제약사항:**) describing structural data quality issues that will limit guide accuracy — extremely short descriptions, missing CVSS versions, complex CPE AND-logic, unusual EPSS values, etc.

## 4. 권장 테스트 케이스

Pipe-formatted table with columns: | 파일명 | 제거 항목 | 테스트 목적 |

Always include full.json (no removals, baseline) as the first row.

Rules for case design:
- Only propose cases that are meaningfully different from each other and from full.json.
- Do not propose cases for fields that are already empty or null in full.json.
- Each case name becomes its file name (e.g. no-fkie-nvd.json, no-cross-refs.json, minimal.json).
- minimal.json is the absolute floor: only core fields plus whatever ghost sources remain in data_sources.
```

---

## Ghost Sources — Definition

A ghost source is a name that appears in `data_sources` but has no corresponding data block anywhere in the JSON (the `cross_references.{name}` key either does not exist, is `[]`, or is `{}`). Ghost sources must **not** be removed from `data_sources` in any test case — their presence is intentional, testing whether the model fabricates content for named-but-empty sources.

---

## Style Rules

- Tables must be pipe-formatted markdown.
- No section may be omitted even if its content is minimal — write "해당 없음" where applicable.
- Do not add sections beyond the four defined above.
- Do not add a TL;DR, introduction, or conclusion block.
