# Agent Prompt — Generate Context Variations

## Reference Documents

**Before producing any file, read these existing variant JSONs to calibrate the transformation pattern and JSON structure:**

- `contexts/cve-1999-0016/no-fkie-nvd.json`
- `contexts/cve-1999-0016/no-cross-refs.json`
- `contexts/cve-1999-0016/minimal.json`
- `contexts/cve-2024-3400/no-fkie-nvd.json`
- `contexts/cve-2024-3400/no-remediation.json`
- `contexts/cve-2024-3400/minimal.json`

The output for any new CVE must match those files exactly in JSON structure, field ordering, and transformation logic. Do not introduce new keys or restructure the JSON in any way.

---

## Task

For each CVE ID that has an `analyses/{cve_id}.md` but does **not** yet have all of its non-`full` context variant JSONs, read the analysis and `contexts/{cve_id}/full.json`, then produce the missing variant files.

## Input

- `analyses/{cve_id}.md` — section 4 ("권장 테스트 케이스") defines the required variants and what each removes.
- `contexts/{cve_id}/full.json` — the base file all variants are derived from.

## Discovery Logic

1. List all CVE IDs under `contexts/` that also have a file at `analyses/{cve_id}.md`.
2. Read section 4 of the analysis to get the full list of required variant file names (e.g. `no-fkie-nvd.json`, `no-cross-refs.json`, `minimal.json`).
3. For each required variant file, check whether it already exists under `contexts/{cve_id}/`.
4. Produce only the files that are missing.

---

## Transformation Rules

Start every variant from a **deep copy** of `full.json`. Apply only the removals specified for that case in the analysis. Do not touch any other field.

### Removing a non-ghost data source

A non-ghost source is one that has an actual data block in the JSON (e.g. `cross_references.fkie_nvd`, `cross_references.ghsa`, `cross_references.csaf`, `threat_intel.kev`, `remediation`, etc.).

When a case removes a non-ghost source, **both** of the following must be done — omitting either is an error:

1. Remove the source's name from the `data_sources` array.
2. Remove (or null out, if the field must remain structurally) the corresponding data block from the JSON body.

### Ghost sources — do not touch

A ghost source is a name in `data_sources` that has no corresponding data block in the JSON (e.g. `gsd`, `variot`, `fstec`, `cnvd`, `certfr_avis`, `certfr_alerte`). Ghost sources must be left in `data_sources` as-is in every variant, including `minimal.json`. Their presence is intentional — it tests whether the model fabricates content for named-but-empty sources.

### `minimal.json`

Remove everything except `core` and any ghost sources remaining in `data_sources`. Specifically:
- Remove all of `cross_references`.
- Remove all of `threat_intel`.
- Remove all other non-core data blocks as applicable.
- Leave ghost source names in `data_sources`.

---

## Output

One JSON file per variant, written to `contexts/{cve_id}/{variant_name}.json`.

The file must be valid, well-formatted JSON (2-space indentation, same as `full.json`). Do not alter the top-level key order relative to `full.json` — only remove keys, never reorder or rename them.
