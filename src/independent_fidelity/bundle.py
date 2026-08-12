"""Deterministic, inert read-only projection for Independent Fidelity Evidence."""

from __future__ import annotations

import difflib
import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from bs4 import BeautifulSoup

from src.independent_fidelity.contracts import (
    ContractError,
    PROJECTION_IDENTITY_ALGORITHM,
    bytes_sha256,
    semantic_sha256,
    validate_evidence,
    with_evidence_semantic_identity,
)
from src.independent_fidelity.verifier import VerificationRun


class EvidenceBundleError(ValueError):
    """An Evidence bundle path, hash, or projection is unsafe or inconsistent."""


class _DuplicateJsonKey(ValueError):
    pass


_CSP = (
    "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; "
    "img-src 'none'; media-src 'none'; font-src 'none'; connect-src 'none'; "
    "object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none';"
)


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise EvidenceBundleError(f"Unsafe Evidence reference: {value}")
    return path


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is forbidden: {value}")


def _load_evidence_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise EvidenceBundleError(
            f"Evidence JSON is not strict closed-world JSON: {error}"
        ) from error
    if not isinstance(value, dict):
        raise EvidenceBundleError("Evidence JSON root must be an object")
    return value


def _write_new(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise EvidenceBundleError(f"Evidence artifact already exists: {path}")
    path.write_bytes(value)


def _diff_document(expected: str, payload: str, *, state_id: str) -> str:
    diff = _diff_text(expected, payload, state_id=state_id)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<meta http-equiv=\"Content-Security-Policy\" content=\"{html.escape(_CSP, quote=False)}\">"
        "<title>Inert evidence diff</title></head><body>"
        f"<pre>{html.escape(diff)}</pre></body></html>"
    )


def _diff_text(expected: str, payload: str, *, state_id: str) -> str:
    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            payload.splitlines(keepends=True),
            fromfile=f"{state_id}.expected.html",
            tofile=f"{state_id}.payload.html",
        )
    )
    if not diff:
        diff = "No differences.\n"
    return diff


def _criteria_text(criteria: list[Mapping[str, Any]]) -> str:
    return ", ".join(
        f"{item['filterKey']}={item['matchValues']}" for item in criteria
    ) or "(unfiltered)"


def _coverage_text(value: Any) -> str:
    if not isinstance(value, Mapping):
        return str(value)
    if {"universe_count", "selected_count", "untested_count"}.issubset(value):
        return (
            f"{value['selected_count']}/{value['universe_count']} selected; "
            f"untested={value['untested_count']}"
        )
    if {"required", "completed", "passed", "failed", "blocked"}.issubset(value):
        return (
            f"required={value['required']}; completed={value['completed']}; "
            f"passed={value['passed']}; failed={value['failed']}; "
            f"blocked={value['blocked']}"
        )
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _l3a_artifact_rows(summary: Mapping[str, Any]) -> str:
    labels = (
        ("validation", "Validation"),
        ("sampling_plan", "Sampling Plan"),
        ("sampled_content_evidence", "Sampled Content Evidence"),
    )
    rows: list[str] = []
    for key, label in labels:
        reference = summary.get(key)
        if not isinstance(reference, Mapping):
            continue
        details = [
            f"path={reference.get('path', 'N/A')}",
            f"sha256={reference.get('sha256', 'N/A')}",
        ]
        for identity_key in ("evidence_sha256", "plan_sha256"):
            if identity_key in reference:
                details.append(f"{identity_key}={reference[identity_key]}")
        rows.append(
            f"<dt>{html.escape(label)}</dt><dd><code>"
            f"{html.escape('; '.join(str(value) for value in details))}"
            "</code></dd>"
        )
    legacy = summary.get("evidence_reference")
    if legacy is not None and not rows:
        rows.append(
            "<dt>Evidence reference</dt>"
            f"<dd><code>{html.escape(str(legacy))}</code></dd>"
        )
    return "".join(rows)


def _render_review(
    evidence: Mapping[str, Any],
    fragments: Mapping[str, str],
    *,
    l3a_summary: Mapping[str, Any],
    style_variant: str,
    projection_warnings: Sequence[Mapping[str, Any]] = (),
) -> str:
    base_style = """
body{font-family:ui-sans-serif,system-ui,sans-serif;margin:1rem;color:#18202a}
nav a{margin-right:.6rem}.claims,.meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem}
.claim-card,.hygiene{border:1px solid #d0d5dd;padding:.75rem}.hygiene{margin:1rem 0;background:#fffaeb}
.state{border-top:2px solid #667085;margin-top:1.5rem;padding-top:1rem}
.compare{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f8;padding:.75rem;border:1px solid #d0d5dd}
dt{font-weight:700}dd{margin:0 0 .45rem}.verdict{font-weight:700}
"""
    style = base_style + f"\n/* projection-variant:{html.escape(style_variant)} */\n"
    identity = evidence["identity"]
    state_links = " ".join(
        f'<a href="#state-{index:03d}">{html.escape(state["state_id"])}</a>'
        for index, state in enumerate(evidence["states"], start=1)
    )
    sections: list[str] = []
    states = evidence["states"]
    for index, state in enumerate(states, start=1):
        previous_link = (
            f'<a href="#state-{index - 1:03d}">上一状态</a>'
            if index > 1
            else "<span>上一状态</span>"
        )
        next_link = (
            f'<a href="#state-{index + 1:03d}">下一状态</a>'
            if index < len(states)
            else "<span>下一状态</span>"
        )
        source = html.escape(fragments[state["source"]["path"]])
        expected = html.escape(fragments[state["expected"]["path"]])
        payload = html.escape(fragments[state["payload"]["path"]])
        locator = html.escape(
            json.dumps(state["locator"], ensure_ascii=False, sort_keys=True)
        )
        mismatch_text = html.escape(
            json.dumps(state["mismatches"], ensure_ascii=False, indent=2)
        )
        error_text = html.escape(
            json.dumps(state["blocking_errors"], ensure_ascii=False, indent=2)
        )
        diff_text = html.escape(
            _diff_text(
                fragments[state["expected"]["path"]],
                fragments[state["payload"]["path"]],
                state_id=state["state_id"],
            )
        )
        sections.append(
            f"""
<section class="state" id="state-{index:03d}">
  <nav>{previous_link} | {next_link}</nav>
  <h2>{html.escape(state['state_id'])}</h2>
  <p class="verdict">L3b: {html.escape(state['verdict'])}</p>
  <dl class="meta">
    <div><dt>Filter criteria</dt><dd>{html.escape(_criteria_text(state['criteria']))}</dd></div>
    <div><dt>Locator</dt><dd><code>{locator}</code></dd></div>
    <div><dt>Retained tables</dt><dd>{html.escape(', '.join(state['retained_table_ids']) or '—')}</dd></div>
    <div><dt>Removed tables</dt><dd>{html.escape(', '.join(state['removed_table_ids']) or '—')}</dd></div>
    <div><dt>Applied transforms</dt><dd>{html.escape(', '.join(state['applied_transform_rule_ids']) or '—')}</dd></div>
    <div><dt>SHA</dt><dd>source={state['source']['sha256']}<br>expected={state['expected']['sha256']}<br>payload={state['payload']['sha256']}</dd></div>
  </dl>
  <div class="compare">
    <article><h3>原始 Source</h3><pre><code>{source}</code></pre></article>
    <article><h3>转换后 Expected</h3><pre><code>{expected}</code></pre></article>
    <article><h3>Persisted Payload</h3><pre><code>{payload}</code></pre></article>
  </div>
  <h3>Diff</h3><pre>{diff_text}</pre>
  <h3>Comparison mismatches</h3><pre>{mismatch_text}</pre>
  <h3>Blocking errors</h3><pre>{error_text}</pre>
</section>"""
        )
    qualification = evidence["qualification_limitation"] or "—"
    blocked = evidence["blocked_reason"] or "—"
    basis = evidence["reconstruction_basis"]
    profile = evidence["verifier_profile"]
    l3a_coverage = _coverage_text(l3a_summary.get("coverage", "N/A"))
    l3b_coverage = _coverage_text(evidence["coverage"])
    hygiene = ""
    if projection_warnings:
        warning_text = html.escape(
            json.dumps(
                list(projection_warnings),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        hygiene = f"""
<section class="hygiene" id="configuration-hygiene">
  <h2>Configuration Hygiene</h2>
  <p>Nonblocking deterministic configuration findings; verdict effect: none.</p>
  <pre>{warning_text}</pre>
</section>"""
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{html.escape(_CSP, quote=False)}">
<meta name="referrer" content="no-referrer"><title>Independent Fidelity Evidence Review</title>
<style>{style}</style></head><body>
<h1>Independent Fidelity Evidence Review</h1>
<p>{html.escape(identity['product_key'])} · {html.escape(identity['language'])} · {html.escape(identity['item_id'])}</p>
<div class="claims">
  <section class="claim-card"><h2>L3a / current Machine Validation</h2>
    <p>Stored claim: <code>{html.escape(str(l3a_summary['claim']))}</code><br>
    Verdict: <strong>{html.escape(str(l3a_summary['verdict']))}</strong><br>
    Coverage: {html.escape(l3a_coverage)}</p>
    <dl>{_l3a_artifact_rows(l3a_summary)}</dl>
  </section>
  <section class="claim-card"><h2>L3b / Independent Fidelity</h2>
    <p>Claim: <code>{html.escape(str(evidence['claim']))}</code><br>
    Verdict: <strong>{html.escape(str(evidence['verdict']))}</strong><br>
    Coverage: {html.escape(l3b_coverage)}</p>
    <dl>
      <dt>Reconstruction Basis</dt><dd><code>{html.escape(str(basis['basis_id']))}; semantic_sha256={basis['basis_semantic_identity']['sha256']}</code></dd>
      <dt>Verifier Profile</dt><dd><code>id={html.escape(str(profile['id']))}; version={html.escape(str(profile['version']))}; path={html.escape(str(profile['path']))}; sha256={profile['sha256']}</code></dd>
      <dt>Algorithm identities</dt><dd><code>reconstruction={html.escape(str(evidence['reconstruction_profile_version']))}; wire={html.escape(str(evidence['wire_transform_version']))}; comparison={html.escape(str(evidence['comparison_version']))}</code></dd>
      <dt>Evidence semantic identity</dt><dd><code>{evidence['evidence_semantic_identity']['algorithm']}={evidence['evidence_semantic_identity']['sha256']}</code></dd>
    </dl>
  </section>
</div>
<p>Qualification limitation: {html.escape(str(qualification))}<br>Blocked reason: {html.escape(str(blocked))}</p>
{hygiene}
<nav aria-label="状态选择器">{state_links}</nav>
{''.join(sections)}
</body></html>"""


def build_evidence_bundle(
    bundle_root: str | Path,
    *,
    repository_root: str | Path,
    run: VerificationRun,
    l3a_summary: Mapping[str, Any],
    style_variant: str = "default-v1",
) -> dict[str, Any]:
    """Write fragments, display-only diffs, review.html, and evidence.json."""

    root = Path(bundle_root).resolve()
    repository_root = Path(repository_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise EvidenceBundleError(f"Evidence bundle directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)

    evidence = with_evidence_semantic_identity(run.evidence)
    for relative_path, content in sorted(run.fragments.items()):
        _write_new(root / _safe_relative(relative_path), content.encode("utf-8"))
    diff_artifacts: list[dict[str, str]] = []
    for state in evidence["states"]:
        expected = run.fragments[state["expected"]["path"]]
        payload = run.fragments[state["payload"]["path"]]
        diff = _diff_document(expected, payload, state_id=state["state_id"])
        path = _safe_relative(state["diff"]["path"])
        value = diff.encode("utf-8")
        _write_new(root / path, value)
        diff_artifacts.append(
            {"path": path.as_posix(), "sha256": bytes_sha256(value)}
        )

    review = _render_review(
        evidence,
        run.fragments,
        l3a_summary=l3a_summary,
        style_variant=style_variant,
        projection_warnings=run.projection_warnings,
    )
    review_bytes = review.encode("utf-8")
    _write_new(root / "review.html", review_bytes)
    projection_artifacts = [
        {"path": "review.html", "sha256": bytes_sha256(review_bytes)},
        *diff_artifacts,
    ]
    evidence["review_projection_artifact_identity"] = {
        "algorithm": PROJECTION_IDENTITY_ALGORITHM,
        "artifacts": projection_artifacts,
        "sha256": semantic_sha256(projection_artifacts),
    }
    validated = validate_evidence(repository_root, evidence)
    _write_new(
        root / "evidence.json",
        (
            json.dumps(
                validated, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n"
        ).encode("utf-8"),
    )
    verify_evidence_bundle(repository_root, root)
    return validated


def _bound_file(bundle_root: Path, relative_path: str) -> Path:
    relative = _safe_relative(relative_path)
    root = bundle_root.resolve()
    if bundle_root.is_symlink():
        raise EvidenceBundleError("Evidence bundle root cannot be a symbolic link")
    candidate = bundle_root / relative
    cursor = bundle_root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise EvidenceBundleError(
                f"Evidence reference contains a symbolic link: {relative_path}"
            )
    path = candidate.resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise EvidenceBundleError(
            f"Evidence reference escapes bundle: {relative_path}"
        ) from error
    if not candidate.is_file():
        raise EvidenceBundleError(f"Evidence artifact is missing: {relative_path}")
    return candidate


_FORBIDDEN_PROJECTION_TAGS = {
    "script",
    "form",
    "img",
    "video",
    "audio",
    "iframe",
    "object",
    "embed",
    "link",
    "base",
    "source",
    "track",
}
_URL_ATTRIBUTES = {
    "src",
    "srcset",
    "action",
    "formaction",
    "poster",
    "data",
    "ping",
}


def _verify_inert_document(path: Path, *, allow_anchors: bool) -> None:
    try:
        document = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise EvidenceBundleError(
            f"Projection document is not strict UTF-8: {path.name}: {error}"
        ) from error
    soup = BeautifulSoup(document, "html.parser")
    csp = soup.select('meta[http-equiv="Content-Security-Policy"]')
    if len(csp) != 1 or csp[0].get("content") != _CSP:
        raise EvidenceBundleError(
            f"Projection document does not contain the exact inert CSP: {path.name}"
        )
    forbidden = [tag.name for tag in soup.find_all(_FORBIDDEN_PROJECTION_TAGS)]
    if forbidden:
        raise EvidenceBundleError(
            f"Projection document contains active/resource tags: {path.name}: {forbidden}"
        )
    for tag in soup.find_all(True):
        if (
            tag.name == "meta"
            and tag.has_attr("http-equiv")
            and str(tag.get("http-equiv")).lower()
            != "content-security-policy"
        ):
            raise EvidenceBundleError(
                f"Projection document contains active meta http-equiv: {path.name}"
            )
        if tag.name == "style" and any(
            token in tag.get_text().lower() for token in ("url(", "@import")
        ):
            raise EvidenceBundleError(
                f"Projection stylesheet can request an external resource: {path.name}"
            )
        for attribute, value in tag.attrs.items():
            lowered = str(attribute).lower()
            if lowered.startswith("on") or lowered in _URL_ATTRIBUTES:
                raise EvidenceBundleError(
                    f"Projection document contains active URL/event attribute: "
                    f"{path.name}: {tag.name}[{attribute}]"
                )
            if lowered == "style" and any(
                token in str(value).lower() for token in ("url(", "@import")
            ):
                raise EvidenceBundleError(
                    f"Projection inline style can request an external resource: "
                    f"{path.name}: {tag.name}[style]"
                )
            if lowered != "href":
                continue
            if not allow_anchors or not isinstance(value, str) or not value.startswith("#"):
                raise EvidenceBundleError(
                    f"Projection navigation must be a same-document anchor: "
                    f"{path.name}: {value!r}"
                )


def verify_inert_projection(
    bundle_root: str | Path,
    evidence: Mapping[str, Any],
) -> None:
    """Verify review/diff documents are inert even when opened directly."""

    root = Path(bundle_root).resolve()
    _verify_inert_document(
        _bound_file(root, "review.html"), allow_anchors=True
    )
    for state in evidence["states"]:
        _verify_inert_document(
            _bound_file(root, state["diff"]["path"]),
            allow_anchors=False,
        )


def verify_evidence_bundle(
    repository_root: str | Path,
    bundle_root: str | Path,
) -> dict[str, Any]:
    repository_root = Path(repository_root).resolve()
    bundle_root = Path(bundle_root).resolve()
    evidence_path = _bound_file(bundle_root, "evidence.json")
    evidence = _load_evidence_json(evidence_path)
    try:
        validated = validate_evidence(repository_root, evidence)
    except ContractError as error:
        raise EvidenceBundleError(str(error)) from error
    for state in validated["states"]:
        for key in ("source", "expected", "payload"):
            reference = state[key]
            if not reference["path"].endswith(".html.txt"):
                raise EvidenceBundleError(
                    "Raw Source/Expected/Payload fragments must use .html.txt: "
                    f"{reference['path']}"
                )
            path = _bound_file(bundle_root, reference["path"])
            if bytes_sha256(path.read_bytes()) != reference["sha256"]:
                raise EvidenceBundleError(
                    f"Evidence fragment SHA drifted: {reference['path']}"
                )
        _bound_file(bundle_root, state["diff"]["path"])
    projection = validated["review_projection_artifact_identity"]
    actual_artifacts = []
    for reference in projection["artifacts"]:
        path = _bound_file(bundle_root, reference["path"])
        digest = bytes_sha256(path.read_bytes())
        if digest != reference["sha256"]:
            raise EvidenceBundleError(
                f"Review projection SHA drifted: {reference['path']}"
            )
        actual_artifacts.append(
            {"path": reference["path"], "sha256": digest}
        )
    if semantic_sha256(actual_artifacts) != projection["sha256"]:
        raise EvidenceBundleError("Review projection artifact identity drifted")
    verify_inert_projection(bundle_root, validated)
    return validated
