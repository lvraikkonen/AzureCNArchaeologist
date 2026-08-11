export type ReviewLanguage = "zh-cn" | "en-us";
export type ReviewStatus = "not_requested" | "pending" | "approved" | "rejected";
export type EvidenceBinding = "not_applicable" | "bound" | "stale";
export type ApprovalEligibility = "blocked" | "eligible";
export type InspectionMode = "interactive" | "full";

export interface ReviewArtifact {
  path: string;
  sha256: string | null;
}

export interface ReviewState {
  state_id: string;
  criteria: [string, string][];
}

export interface ReviewBlocker {
  code: string;
  message: string;
  path?: string;
}

export interface ReviewFinding extends ReviewBlocker {
  classification?: "advisory" | "approval_blocking" | "unknown";
}

export interface ReviewDecisionSummary {
  decision_id: string;
  path: string;
  sha256: string;
  reviewer: string;
  decided_at: string;
  verdict: "approved" | "rejected";
  reason: string | null;
  supersedes_decision_id: string | null;
}

export interface ReviewDecisionHistory extends ReviewDecisionSummary {
  notes: string;
  inspected_states: Record<string, unknown>[];
}

export interface ReviewQueueItem {
  item_id: string;
  product_key: string;
  resource_key: string;
  language: ReviewLanguage;
  page_model: string;
  strategy: string;
  status: {
    execution: string;
    validation: string;
    review: ReviewStatus;
    publication: string;
    evidence_binding: EvidenceBinding;
    approval_eligibility: ApprovalEligibility;
    release: string;
  };
  artifacts: Record<
    | "payload"
    | "diagnostic"
    | "validation"
    | "sampling_plan"
    | "sampled_content_evidence"
    | "current_review_decision",
    ReviewArtifact | null
  >;
  bindings: {
    source_sha256: string;
    payload_sha256: string;
    validation_artifact_sha256: string;
    validation_evidence_sha256: string;
    sampling_plan_sha256: string | null;
  };
  coverage: {
    mode: "full" | "stratified_sample";
    universe_count: number;
    selected_count: number;
    untested_count: number;
    selected_state_ids: string[];
  };
  inspection: {
    mode: InspectionMode;
    state_universe: ReviewState[];
    full_content_scope: boolean;
  };
  source_quality_findings: ReviewFinding[];
  approval_blockers: ReviewBlocker[];
  current_decision: ReviewDecisionSummary | null;
  release_eligibility: {
    eligible: boolean;
    blockers: ReviewBlocker[];
  };
  source_warning: boolean;
  approval_blocked: boolean;
  machine_failed: boolean;
  release_ready: boolean;
}

export interface WorkbenchProjection {
  schema_version: "1.0";
  projection_id: string;
  generated_at: string;
  batch: {
    batch_id: string;
    manifest_revision: number;
    status: string;
    validation_profile_id: string;
    run_dir: string;
  };
  summary: {
    items: Record<string, number>;
    products: {
      total: number;
      release_ready_count: number;
      pending_attention: number;
      rejected_attention: number;
      source_warning_count: number;
      approval_blocked_count: number;
      machine_failed_count: number;
    };
  };
  history: {
    configured: boolean;
    batches: { batch_id: string; label?: string }[];
  };
  release: {
    release_manifests: ReviewArtifact[];
    publication_receipts: ReviewArtifact[];
  };
  items: ReviewQueueItem[];
}

export interface ManualComparison {
  status: "matched" | "mismatched";
  source_fingerprint: string;
  payload_fingerprint: string;
  source: unknown;
  payload: unknown;
  diff: unknown;
}

export interface ItemEvidence {
  schema_version: "1.0";
  generated_at: string;
  batch_id: string;
  item_id: string;
  manifest_revision: number;
  item: {
    language: ReviewLanguage;
    resource_key: string;
    product_key: string;
    page_model: string;
    strategy: string;
    slug: string;
    source_url: string | null;
  };
  status: ReviewQueueItem["status"];
  artifacts: Pick<
    ReviewQueueItem["artifacts"],
    | "payload"
    | "validation"
    | "sampling_plan"
    | "sampled_content_evidence"
    | "current_review_decision"
  >;
  bindings: ReviewQueueItem["bindings"];
  coverage: Record<string, unknown>;
  validation_summary: {
    status: "passed" | "failed";
    evidence_sha256: string;
    errors: unknown[];
    warnings: unknown[];
    approval_preconditions: Record<string, unknown>;
  };
  source_quality_findings: ReviewFinding[];
  machine_evidence: {
    page_global_comparison: Record<string, unknown>;
    full_content_comparison: Record<string, unknown> | null;
    samples: Record<string, unknown>[];
  };
  inspection: {
    mode: InspectionMode;
    allowed_state_ids: string[];
    state_universe: ReviewState[];
  };
  manual_preview: {
    status: "available" | "unavailable";
    error: ReviewBlocker | null;
    page_global: ManualComparison | null;
    full_content: ManualComparison | null;
    states: {
      state_id: string;
      criteria: [string, string][];
      machine_selected: boolean;
      comparison: ManualComparison;
    }[];
  };
  decisions: {
    current: ReviewDecisionSummary | null;
    history: ReviewDecisionHistory[];
  };
}

export interface ReviewFilters {
  query: string;
  language: "all" | ReviewLanguage;
  review: "all" | ReviewStatus;
  binding: "all" | EvidenceBinding;
  coverage: "all" | "full" | "stratified_sample";
  source: "all" | "warning" | "approval_blocked" | "clear";
  release: "all" | "ready" | "blocked";
}

export const defaultReviewFilters: ReviewFilters = {
  query: "",
  language: "all",
  review: "pending",
  binding: "all",
  coverage: "all",
  source: "all",
  release: "all",
};

const SHA256 = /^[a-f0-9]{64}$/;

function fail(path: string, expectation: string): never {
  throw new TypeError(`Invalid review workbench payload at ${path}: ${expectation}`);
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "expected an object");
  }
  return value as Record<string, unknown>;
}

function exact(value: Record<string, unknown>, keys: readonly string[], path: string): void {
  const allowed = new Set(keys);
  for (const key of keys) {
    if (!(key in value)) fail(`${path}.${key}`, "is required");
  }
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) fail(`${path}.${key}`, "is not allowed");
  }
}

function stringValue(value: unknown, path: string, nonEmpty = false): string {
  if (typeof value !== "string" || (nonEmpty && value.length === 0)) {
    fail(path, nonEmpty ? "expected a non-empty string" : "expected a string");
  }
  return value;
}

function nullableString(value: unknown, path: string): void {
  if (value !== null && typeof value !== "string") fail(path, "expected a string or null");
}

function numberValue(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    fail(path, "expected a non-negative integer");
  }
  return value;
}

function booleanValue(value: unknown, path: string): void {
  if (typeof value !== "boolean") fail(path, "expected a boolean");
}

function arrayValue(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) fail(path, "expected an array");
  return value;
}

function enumValue(value: unknown, allowed: readonly string[], path: string): string {
  if (typeof value !== "string" || !allowed.includes(value)) {
    fail(path, `expected one of ${allowed.join(", ")}`);
  }
  return value;
}

function sha(value: unknown, path: string): void {
  if (typeof value !== "string" || !SHA256.test(value)) {
    fail(path, "expected a lowercase SHA-256 string");
  }
}

function nullableSha(value: unknown, path: string): void {
  if (value !== null) sha(value, path);
}

function artifact(value: unknown, path: string): void {
  if (value === null) return;
  const item = record(value, path);
  exact(item, ["path", "sha256"], path);
  stringValue(item.path, `${path}.path`, true);
  nullableSha(item.sha256, `${path}.sha256`);
}

function blocker(value: unknown, path: string): void {
  const item = record(value, path);
  for (const key of Object.keys(item)) {
    if (!["code", "message", "path"].includes(key)) fail(`${path}.${key}`, "is not allowed");
  }
  stringValue(item.code, `${path}.code`, true);
  stringValue(item.message, `${path}.message`, true);
  if ("path" in item) stringValue(item.path, `${path}.path`);
}

function finding(value: unknown, path: string): void {
  const item = record(value, path);
  for (const key of Object.keys(item)) {
    if (!["code", "message", "path", "classification"].includes(key)) fail(`${path}.${key}`, "is not allowed");
  }
  stringValue(item.code, `${path}.code`, true);
  stringValue(item.message, `${path}.message`, true);
  if ("path" in item) stringValue(item.path, `${path}.path`);
  if ("classification" in item) enumValue(item.classification, ["advisory", "approval_blocking", "unknown"], `${path}.classification`);
}

function state(value: unknown, path: string): void {
  const item = record(value, path);
  exact(item, ["state_id", "criteria"], path);
  sha(item.state_id, `${path}.state_id`);
  arrayValue(item.criteria, `${path}.criteria`).forEach((entry, index) => {
    const pair = arrayValue(entry, `${path}.criteria[${index}]`);
    if (pair.length !== 2) fail(`${path}.criteria[${index}]`, "expected a [filterKey, value] pair");
    stringValue(pair[0], `${path}.criteria[${index}][0]`, true);
    stringValue(pair[1], `${path}.criteria[${index}][1]`, true);
  });
}

function decisionSummary(value: unknown, path: string, history = false): void {
  if (value === null && !history) return;
  const item = record(value, path);
  exact(
    item,
    history
      ? [
          "decision_id",
          "path",
          "sha256",
          "reviewer",
          "decided_at",
          "verdict",
          "reason",
          "notes",
          "inspected_states",
          "supersedes_decision_id",
        ]
      : [
          "decision_id",
          "path",
          "sha256",
          "reviewer",
          "decided_at",
          "verdict",
          "reason",
          "supersedes_decision_id",
        ],
    path,
  );
  sha(item.decision_id, `${path}.decision_id`);
  stringValue(item.path, `${path}.path`, true);
  sha(item.sha256, `${path}.sha256`);
  stringValue(item.reviewer, `${path}.reviewer`, true);
  stringValue(item.decided_at, `${path}.decided_at`, true);
  enumValue(item.verdict, ["approved", "rejected"], `${path}.verdict`);
  nullableString(item.reason, `${path}.reason`);
  nullableSha(item.supersedes_decision_id, `${path}.supersedes_decision_id`);
  if (history) {
    stringValue(item.notes, `${path}.notes`);
    arrayValue(item.inspected_states, `${path}.inspected_states`);
  }
}

function bindings(value: unknown, path: string): void {
  const item = record(value, path);
  exact(
    item,
    [
      "source_sha256",
      "payload_sha256",
      "validation_artifact_sha256",
      "validation_evidence_sha256",
      "sampling_plan_sha256",
    ],
    path,
  );
  sha(item.source_sha256, `${path}.source_sha256`);
  sha(item.payload_sha256, `${path}.payload_sha256`);
  sha(item.validation_artifact_sha256, `${path}.validation_artifact_sha256`);
  sha(item.validation_evidence_sha256, `${path}.validation_evidence_sha256`);
  nullableSha(item.sampling_plan_sha256, `${path}.sampling_plan_sha256`);
}

function queueItem(value: unknown, path: string): void {
  const item = record(value, path);
  exact(
    item,
    [
      "item_id",
      "product_key",
      "resource_key",
      "language",
      "page_model",
      "strategy",
      "status",
      "artifacts",
      "bindings",
      "coverage",
      "inspection",
      "source_quality_findings",
      "approval_blockers",
      "current_decision",
      "release_eligibility",
      "source_warning",
      "approval_blocked",
      "machine_failed",
      "release_ready",
    ],
    path,
  );
  stringValue(item.item_id, `${path}.item_id`, true);
  stringValue(item.product_key, `${path}.product_key`, true);
  stringValue(item.resource_key, `${path}.resource_key`, true);
  enumValue(item.language, ["zh-cn", "en-us"], `${path}.language`);
  stringValue(item.page_model, `${path}.page_model`, true);
  stringValue(item.strategy, `${path}.strategy`, true);
  const status = record(item.status, `${path}.status`);
  exact(status, ["execution", "validation", "review", "publication", "evidence_binding", "approval_eligibility", "release"], `${path}.status`);
  stringValue(status.execution, `${path}.status.execution`, true);
  stringValue(status.validation, `${path}.status.validation`, true);
  enumValue(status.review, ["not_requested", "pending", "approved", "rejected"], `${path}.status.review`);
  stringValue(status.publication, `${path}.status.publication`, true);
  enumValue(status.evidence_binding, ["not_applicable", "bound", "stale"], `${path}.status.evidence_binding`);
  enumValue(status.approval_eligibility, ["blocked", "eligible"], `${path}.status.approval_eligibility`);
  stringValue(status.release, `${path}.status.release`, true);
  const artifacts = record(item.artifacts, `${path}.artifacts`);
  exact(artifacts, ["payload", "diagnostic", "validation", "sampling_plan", "sampled_content_evidence", "current_review_decision"], `${path}.artifacts`);
  Object.entries(artifacts).forEach(([key, value]) => artifact(value, `${path}.artifacts.${key}`));
  bindings(item.bindings, `${path}.bindings`);
  const coverage = record(item.coverage, `${path}.coverage`);
  exact(coverage, ["mode", "universe_count", "selected_count", "untested_count", "selected_state_ids"], `${path}.coverage`);
  enumValue(coverage.mode, ["full", "stratified_sample"], `${path}.coverage.mode`);
  numberValue(coverage.universe_count, `${path}.coverage.universe_count`);
  numberValue(coverage.selected_count, `${path}.coverage.selected_count`);
  numberValue(coverage.untested_count, `${path}.coverage.untested_count`);
  arrayValue(coverage.selected_state_ids, `${path}.coverage.selected_state_ids`).forEach((value, index) => sha(value, `${path}.coverage.selected_state_ids[${index}]`));
  const inspection = record(item.inspection, `${path}.inspection`);
  exact(inspection, ["mode", "state_universe", "full_content_scope"], `${path}.inspection`);
  enumValue(inspection.mode, ["interactive", "full"], `${path}.inspection.mode`);
  arrayValue(inspection.state_universe, `${path}.inspection.state_universe`).forEach((value, index) => state(value, `${path}.inspection.state_universe[${index}]`));
  booleanValue(inspection.full_content_scope, `${path}.inspection.full_content_scope`);
  arrayValue(item.source_quality_findings, `${path}.source_quality_findings`).forEach((value, index) => finding(value, `${path}.source_quality_findings[${index}]`));
  arrayValue(item.approval_blockers, `${path}.approval_blockers`).forEach((value, index) => blocker(value, `${path}.approval_blockers[${index}]`));
  decisionSummary(item.current_decision, `${path}.current_decision`);
  const release = record(item.release_eligibility, `${path}.release_eligibility`);
  exact(release, ["eligible", "blockers"], `${path}.release_eligibility`);
  booleanValue(release.eligible, `${path}.release_eligibility.eligible`);
  arrayValue(release.blockers, `${path}.release_eligibility.blockers`).forEach((value, index) => blocker(value, `${path}.release_eligibility.blockers[${index}]`));
  booleanValue(item.source_warning, `${path}.source_warning`);
  booleanValue(item.approval_blocked, `${path}.approval_blocked`);
  booleanValue(item.machine_failed, `${path}.machine_failed`);
  booleanValue(item.release_ready, `${path}.release_ready`);
}

export function assertWorkbenchProjection(value: unknown): asserts value is WorkbenchProjection {
  const root = record(value, "$");
  exact(root, ["schema_version", "projection_id", "generated_at", "batch", "summary", "history", "release", "items"], "$");
  enumValue(root.schema_version, ["1.0"], "$.schema_version");
  sha(root.projection_id, "$.projection_id");
  stringValue(root.generated_at, "$.generated_at", true);
  const batch = record(root.batch, "$.batch");
  exact(batch, ["batch_id", "manifest_revision", "status", "validation_profile_id", "run_dir"], "$.batch");
  stringValue(batch.batch_id, "$.batch.batch_id", true);
  numberValue(batch.manifest_revision, "$.batch.manifest_revision");
  stringValue(batch.status, "$.batch.status", true);
  stringValue(batch.validation_profile_id, "$.batch.validation_profile_id", true);
  stringValue(batch.run_dir, "$.batch.run_dir", true);
  const summary = record(root.summary, "$.summary");
  exact(summary, ["items", "products"], "$.summary");
  Object.entries(record(summary.items, "$.summary.items")).forEach(([key, value]) => numberValue(value, `$.summary.items.${key}`));
  const products = record(summary.products, "$.summary.products");
  exact(products, ["total", "release_ready_count", "pending_attention", "rejected_attention", "source_warning_count", "approval_blocked_count", "machine_failed_count"], "$.summary.products");
  Object.entries(products).forEach(([key, value]) => numberValue(value, `$.summary.products.${key}`));
  const history = record(root.history, "$.history");
  exact(history, ["configured", "batches"], "$.history");
  booleanValue(history.configured, "$.history.configured");
  arrayValue(history.batches, "$.history.batches").forEach((value, index) => {
    const entry = record(value, `$.history.batches[${index}]`);
    for (const key of Object.keys(entry)) {
      if (!["batch_id", "label"].includes(key)) fail(`$.history.batches[${index}].${key}`, "is not allowed");
    }
    stringValue(entry.batch_id, `$.history.batches[${index}].batch_id`, true);
    if ("label" in entry) stringValue(entry.label, `$.history.batches[${index}].label`, true);
  });
  const release = record(root.release, "$.release");
  exact(release, ["release_manifests", "publication_receipts"], "$.release");
  arrayValue(release.release_manifests, "$.release.release_manifests").forEach((value, index) => artifact(value, `$.release.release_manifests[${index}]`));
  arrayValue(release.publication_receipts, "$.release.publication_receipts").forEach((value, index) => artifact(value, `$.release.publication_receipts[${index}]`));
  arrayValue(root.items, "$.items").forEach((value, index) => queueItem(value, `$.items[${index}]`));
}

function manualComparison(value: unknown, path: string): void {
  const item = record(value, path);
  exact(item, ["status", "source_fingerprint", "payload_fingerprint", "source", "payload", "diff"], path);
  enumValue(item.status, ["matched", "mismatched"], `${path}.status`);
  sha(item.source_fingerprint, `${path}.source_fingerprint`);
  sha(item.payload_fingerprint, `${path}.payload_fingerprint`);
}

export function assertItemEvidence(value: unknown): asserts value is ItemEvidence {
  const root = record(value, "$");
  exact(root, ["schema_version", "generated_at", "batch_id", "item_id", "manifest_revision", "item", "status", "artifacts", "bindings", "coverage", "validation_summary", "source_quality_findings", "machine_evidence", "inspection", "manual_preview", "decisions"], "$");
  enumValue(root.schema_version, ["1.0"], "$.schema_version");
  stringValue(root.generated_at, "$.generated_at", true);
  stringValue(root.batch_id, "$.batch_id", true);
  stringValue(root.item_id, "$.item_id", true);
  numberValue(root.manifest_revision, "$.manifest_revision");
  const item = record(root.item, "$.item");
  exact(item, ["language", "resource_key", "product_key", "page_model", "strategy", "slug", "source_url"], "$.item");
  enumValue(item.language, ["zh-cn", "en-us"], "$.item.language");
  stringValue(item.resource_key, "$.item.resource_key", true);
  stringValue(item.product_key, "$.item.product_key", true);
  stringValue(item.page_model, "$.item.page_model", true);
  stringValue(item.strategy, "$.item.strategy", true);
  stringValue(item.slug, "$.item.slug", true);
  nullableString(item.source_url, "$.item.source_url");
  queueItem(
    {
      item_id: root.item_id,
      product_key: item.product_key,
      resource_key: item.resource_key,
      language: item.language,
      page_model: item.page_model,
      strategy: item.strategy,
      status: root.status,
      artifacts: { ...record(root.artifacts, "$.artifacts"), diagnostic: null },
      bindings: root.bindings,
      coverage: {
        mode: record(root.coverage, "$.coverage").mode,
        universe_count: record(root.coverage, "$.coverage").universe_count,
        selected_count: record(root.coverage, "$.coverage").selected_count,
        untested_count: record(root.coverage, "$.coverage").untested_count,
        selected_state_ids: record(root.coverage, "$.coverage").selected_state_ids,
      },
      inspection: {
        mode: record(root.inspection, "$.inspection").mode,
        state_universe: record(root.inspection, "$.inspection").state_universe,
        full_content_scope: record(root.inspection, "$.inspection").mode === "full",
      },
      source_quality_findings: root.source_quality_findings,
      approval_blockers: [],
      current_decision: record(root.decisions, "$.decisions").current,
      release_eligibility: { eligible: false, blockers: [] },
      source_warning: arrayValue(root.source_quality_findings, "$.source_quality_findings").some((findingValue) => record(findingValue, "$.source_quality_findings[]").classification === "advisory"),
      approval_blocked: false,
      machine_failed: false,
      release_ready: false,
    },
    "$",
  );
  const preview = record(root.manual_preview, "$.manual_preview");
  exact(preview, ["status", "error", "page_global", "full_content", "states"], "$.manual_preview");
  enumValue(preview.status, ["available", "unavailable"], "$.manual_preview.status");
  if (preview.error !== null) blocker(preview.error, "$.manual_preview.error");
  if (preview.page_global !== null) manualComparison(preview.page_global, "$.manual_preview.page_global");
  if (preview.full_content !== null) manualComparison(preview.full_content, "$.manual_preview.full_content");
  arrayValue(preview.states, "$.manual_preview.states").forEach((value, index) => {
    const entry = record(value, `$.manual_preview.states[${index}]`);
    exact(entry, ["state_id", "criteria", "machine_selected", "comparison"], `$.manual_preview.states[${index}]`);
    sha(entry.state_id, `$.manual_preview.states[${index}].state_id`);
    booleanValue(entry.machine_selected, `$.manual_preview.states[${index}].machine_selected`);
    manualComparison(entry.comparison, `$.manual_preview.states[${index}].comparison`);
  });
  const decisions = record(root.decisions, "$.decisions");
  exact(decisions, ["current", "history"], "$.decisions");
  decisionSummary(decisions.current, "$.decisions.current");
  arrayValue(decisions.history, "$.decisions.history").forEach((value, index) => decisionSummary(value, `$.decisions.history[${index}]`, true));
}

export function filterReviewItems(
  items: ReviewQueueItem[],
  filters: ReviewFilters,
): ReviewQueueItem[] {
  const query = filters.query.trim().toLowerCase();
  return items.filter((item) => {
    if (query) {
      const haystack = `${item.product_key} ${item.resource_key} ${item.item_id}`.toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    if (filters.language !== "all" && item.language !== filters.language) return false;
    if (filters.review !== "all" && item.status.review !== filters.review) return false;
    if (filters.binding !== "all" && item.status.evidence_binding !== filters.binding) return false;
    if (filters.coverage !== "all" && item.coverage.mode !== filters.coverage) return false;
    if (filters.source === "warning" && !item.source_warning) return false;
    if (filters.source === "approval_blocked" && !item.approval_blocked) return false;
    if (filters.source === "clear" && (item.source_warning || item.approval_blocked)) return false;
    if (filters.release === "ready" && !item.release_ready) return false;
    if (filters.release === "blocked" && item.release_ready) return false;
    return true;
  });
}

export function decisionLabel(status: ReviewStatus): string {
  return {
    not_requested: "未请求",
    pending: "待审",
    approved: "已批准",
    rejected: "已拒绝",
  }[status];
}

export function bindingLabel(status: EvidenceBinding): string {
  return {
    not_applicable: "未绑定",
    bound: "已绑定",
    stale: "已漂移",
  }[status];
}

export function shortSha(value: string | null | undefined): string {
  return value ? `${value.slice(0, 10)}...` : "—";
}
