"""vgp-workspace-mode-test — CVE guide generation test suite.

Reads all context JSONs from contexts/, generates a guide for each,
and writes results to guides/.

Replicates the dispatch_to_worker flow from src/workspace/llm_dispatcher.py,
running `claude --print` locally instead of inside a vgp-worker container.

Usage:
    uv run main.py [--model MODEL] [--max-threads N]
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_GENERATE_PROMPT_PATH = Path(__file__).parent / "generate.md"
_TRANSLATE_PROMPT_PATH = Path(__file__).parent / "translate.md"
_CONTEXTS_DIR = Path(__file__).parent / "contexts"
_GUIDES_DIR = Path(__file__).parent / "guides"
_GENERATE_LANG = "en"
_TRANSLATE_LANG = "ko"
_MODEL = "claude-sonnet-4-6"

_AUTH_ERROR_PATTERNS = (
    "not logged in",
    "/login",
    "oauth",
    "unauthorized",
    "invalid_api_key",
    "invalid api key",
    "token expired",
    "authentication failed",
)

# Tracks active subprocesses so Ctrl+C can kill them immediately.
_active_procs: set[subprocess.Popen] = set()
_procs_lock = threading.Lock()
_shutdown = threading.Event()


# ---------------------------------------------------------------------------
# Context formatting — mirrors generator._trim_context / _format_user_message
# ---------------------------------------------------------------------------


def _trim_context(context: dict) -> dict:
    ctx = copy.deepcopy(context)
    epss = ctx.get("threat_intel", {}).get("epss")
    if epss and "time-series" in epss:
        del epss["time-series"]
    capecs = ctx.get("weakness_chain", {}).get("capecs", [])
    if len(capecs) > 5:
        ctx["weakness_chain"]["capecs"] = capecs[:5]
        ctx["weakness_chain"]["capecs_truncated"] = len(capecs)
    for cwe in ctx.get("weakness_chain", {}).get("cwes", []):
        if cwe.get("mitigations"):
            cwe["mitigations"] = str(cwe["mitigations"])[:500]
    for capec in ctx.get("weakness_chain", {}).get("capecs", []):
        for key in ("execution_flow", "mitigations", "prerequisites"):
            if capec.get(key):
                capec[key] = str(capec[key])[:500]
    return ctx


def _format_user_message(context: dict, lang: str) -> str:
    return json.dumps(
        {
            "instruction": "Generate a vulnerability onboarding guide from the following context data.",
            "guide_lang": lang,
            "include_reasoning": False,
            "vulnerability_context": _trim_context(context),
        },
        ensure_ascii=False,
        indent=None,
    )


# ---------------------------------------------------------------------------
# Response parsing — mirrors generator._parse_json_response
# ---------------------------------------------------------------------------


def _parse_json_response(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        ).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("json_parse_failed: %s", e)
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Generation — mirrors dispatch_to_worker (local subprocess variant)
# ---------------------------------------------------------------------------


def generate(context: dict, model: str = _MODEL, label: str = "") -> dict | None:
    if _shutdown.is_set():
        return None

    label = label or context.get("cve_id", "unknown")
    logger.info("generating ctx=%s", label)

    proc = subprocess.Popen(
        [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--model",
            model,
            "--system-prompt",
            _GENERATE_PROMPT_PATH.read_text(encoding="utf-8"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    with _procs_lock:
        _active_procs.add(proc)
    try:
        stdout_b, stderr_b = proc.communicate(
            input=_format_user_message(context, _GENERATE_LANG).encode("utf-8")
        )
    finally:
        with _procs_lock:
            _active_procs.discard(proc)

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")

    if proc.returncode != 0:
        logger.error(
            "generate ctx=%s claude exited %d stderr=%s",
            label,
            proc.returncode,
            stderr[:500],
        )
        return None

    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error(
            "generate ctx=%s envelope_parse_failed stdout=%s", label, stdout[:200]
        )
        return None

    if not isinstance(envelope, dict):
        logger.error("generate ctx=%s envelope_not_dict", label)
        return None

    if envelope.get("is_error"):
        result_text = envelope.get("result", "")
        if not isinstance(result_text, str):
            result_text = json.dumps(result_text)
        tag = (
            "auth_error"
            if any(p in result_text.lower() for p in _AUTH_ERROR_PATTERNS)
            else "llm_error"
        )
        logger.error("generate ctx=%s %s: %s", label, tag, result_text[:300])
        return None

    inner = envelope.get("result")
    if not isinstance(inner, str):
        logger.error(
            "generate ctx=%s envelope_result_not_string type=%s",
            label,
            type(inner).__name__,
        )
        return None

    guide = _parse_json_response(inner)
    if guide is None:
        logger.error("generate ctx=%s guide_json_parse_failed", label)
        return None

    usage = envelope.get("usage") or {}
    logger.info(
        "generated ctx=%s input_tokens=%s output_tokens=%s num_turns=%s",
        label,
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        envelope.get("num_turns"),
    )

    guide.setdefault("metadata", {}).update(
        {
            "model": model,
            "prompt_version": "1.0.4",
            "input_tokens": usage.get("input_tokens"),
            "generation_tokens": usage.get("output_tokens"),
            "include_reasoning": False,
        }
    )
    guide["generated_at"] = datetime.now(timezone.utc).isoformat()

    return guide


# ---------------------------------------------------------------------------
# Translation — mirrors generator.translate_guide (workspace subprocess variant)
# ---------------------------------------------------------------------------


def translate(guide: dict, model: str = _MODEL, label: str = "") -> dict | None:
    if _shutdown.is_set():
        return None

    label = label or guide.get("cve_id", "unknown")
    logger.info("translating ctx=%s", label)

    user_message = json.dumps(
        {
            "instruction": f"Translate this vulnerability guide to {_TRANSLATE_LANG}.",
            "target_language": _TRANSLATE_LANG,
            "guide": guide,
        },
        ensure_ascii=False,
    )

    proc = subprocess.Popen(
        [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--model",
            model,
            "--system-prompt",
            _TRANSLATE_PROMPT_PATH.read_text(encoding="utf-8"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    with _procs_lock:
        _active_procs.add(proc)
    try:
        stdout_b, stderr_b = proc.communicate(input=user_message.encode("utf-8"))
    finally:
        with _procs_lock:
            _active_procs.discard(proc)

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")

    if proc.returncode != 0:
        logger.error(
            "translate ctx=%s claude exited %d stderr=%s",
            label,
            proc.returncode,
            stderr[:500],
        )
        return None

    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        logger.error(
            "translate ctx=%s envelope_parse_failed stdout=%s", label, stdout[:200]
        )
        return None

    if not isinstance(envelope, dict):
        logger.error("translate ctx=%s envelope_not_dict", label)
        return None

    if envelope.get("is_error"):
        result_text = envelope.get("result", "")
        if not isinstance(result_text, str):
            result_text = json.dumps(result_text)
        tag = (
            "auth_error"
            if any(p in result_text.lower() for p in _AUTH_ERROR_PATTERNS)
            else "llm_error"
        )
        logger.error("translate ctx=%s %s: %s", label, tag, result_text[:300])
        return None

    inner = envelope.get("result")
    if not isinstance(inner, str):
        logger.error("translate ctx=%s envelope_result_not_string", label)
        return None

    translated = _parse_json_response(inner)
    if translated is None:
        logger.error("translate ctx=%s guide_json_parse_failed", label)
        return None

    usage = envelope.get("usage") or {}
    logger.info(
        "translated ctx=%s input_tokens=%s output_tokens=%s",
        label,
        usage.get("input_tokens"),
        usage.get("output_tokens"),
    )

    translated["lang"] = _TRANSLATE_LANG
    translated["generated_at"] = datetime.now(timezone.utc).isoformat()
    translated.setdefault("metadata", {}).update(
        {
            "model": model,
            "input_tokens": usage.get("input_tokens"),
            "generation_tokens": usage.get("output_tokens"),
        }
    )

    return translated


# ---------------------------------------------------------------------------
# Per-file worker
# ---------------------------------------------------------------------------


def _process_file(ctx_path: Path, model: str) -> None:
    context = json.loads(ctx_path.read_text(encoding="utf-8"))
    base = ctx_path.stem.replace("context", "guide")
    out_dir = _GUIDES_DIR / ctx_path.parent.name
    out_dir.mkdir(parents=True, exist_ok=True)
    label = str(ctx_path.relative_to(_CONTEXTS_DIR).with_suffix(""))

    en_path = out_dir / f"{base}_{_GENERATE_LANG}.json"
    ko_path = out_dir / f"{base}_{_TRANSLATE_LANG}.json"

    if en_path.exists() and ko_path.exists():
        return

    if en_path.exists():
        guide = json.loads(en_path.read_text(encoding="utf-8"))
    else:
        guide = generate(context, model=model, label=label)
        if guide:
            en_path.write_text(json.dumps(guide, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("wrote %s", en_path)
        else:
            logger.error("generate failed ctx=%s", label)

    if guide and not ko_path.exists():
        translated = translate(guide, model=model, label=label)
        if translated:
            ko_path.write_text(json.dumps(translated, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("wrote %s", ko_path)
        else:
            logger.error("translate failed ctx=%s", label)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

    parser = argparse.ArgumentParser(description="CVE guide generation test suite")
    parser.add_argument(
        "--model", default=_MODEL, help=f"Claude model (default: {_MODEL})"
    )
    parser.add_argument(
        "--max-threads",
        type=int,
        default=8,
        help="Max parallel claude processes (default: 1)",
    )
    args = parser.parse_args()

    context_files = sorted(_CONTEXTS_DIR.rglob("*.json"))
    if not context_files:
        logger.error("no context files found in %s", _CONTEXTS_DIR)
        sys.exit(1)

    _GUIDES_DIR.mkdir(parents=True, exist_ok=True)

    executor = ThreadPoolExecutor(max_workers=args.max_threads)
    futures = [executor.submit(_process_file, p, args.model) for p in context_files]
    try:
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error("worker error: %s", e)
    except KeyboardInterrupt:
        logger.info("interrupted — killing subprocesses")
        _shutdown.set()
        with _procs_lock:
            for proc in list(_active_procs):
                try:
                    proc.kill()
                except Exception:
                    pass
        executor.shutdown(wait=False, cancel_futures=True)
        sys.exit(130)
    else:
        executor.shutdown(wait=False)


if __name__ == "__main__":
    main()
