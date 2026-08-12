import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";

import {
  assertIndependentFidelityView,
  assertItemEvidence,
  assertWorkbenchProjection,
  defaultReviewFilters,
  filterReviewItems,
  l3aClaimLabel,
} from "../app/review-model.ts";

const SHA = "a".repeat(64);
const STATE = "b".repeat(64);

function artifact(path = "review/fixture.json", sha256 = SHA) {
  return { path, sha256 };
}

function item(overrides = {}) {
  return {
    item_id: "zh-cn/fixture",
    product_key: "fixture",
    resource_key: "fixture",
    language: "zh-cn",
    page_model: "FlexibleContentPage",
    strategy: "region_filter",
    status: {
      execution: "succeeded",
      validation: "passed",
      review: "pending",
      publication: "not_published",
      evidence_binding: "bound",
      approval_eligibility: "eligible",
      release: "not_released",
    },
    artifacts: {
      payload: artifact("outputs/zh-cn/pricing/fixture.json"),
      diagnostic: artifact("diagnostics/zh-cn/pricing/fixture.sidecar.json"),
      validation: artifact("validation/zh-cn/pricing/fixture.validation.json"),
      sampling_plan: artifact("validation/zh-cn/pricing/fixture.sampling-plan.json"),
      sampled_content_evidence: artifact("validation/zh-cn/pricing/fixture.sampled-content-evidence.json"),
      current_review_decision: null,
    },
    bindings: {
      source_sha256: SHA,
      payload_sha256: SHA,
      validation_artifact_sha256: SHA,
      validation_evidence_sha256: SHA,
      sampling_plan_sha256: SHA,
    },
    coverage: {
      mode: "stratified_sample",
      universe_count: 2,
      selected_count: 1,
      untested_count: 1,
      selected_state_ids: [STATE],
    },
    inspection: {
      mode: "interactive",
      state_universe: [{ state_id: STATE, criteria: [["region", "east"]] }],
      full_content_scope: false,
    },
    source_quality_findings: [],
    approval_blockers: [],
    current_decision: null,
    release_eligibility: { eligible: false, blockers: [{ code: "review_not_approved", message: "pending" }] },
    source_warning: false,
    approval_blocked: false,
    machine_failed: false,
    release_ready: false,
    ...overrides,
  };
}

function projection(overrides = {}) {
  return {
    schema_version: "1.0",
    projection_id: SHA,
    generated_at: "2026-08-03T12:45:00Z",
    batch: {
      batch_id: "20260803T120000Z-deadbeef",
      manifest_revision: 4,
      status: "completed",
      validation_profile_id: "v0.4-validation-p3",
      run_dir: "/tmp/runs/20260803T120000Z-deadbeef",
    },
    summary: {
      items: {
        total: 1,
        reviewable: 1,
        pending: 1,
        approved: 0,
        rejected: 0,
        evidence_bound: 1,
        evidence_stale: 0,
        evidence_not_applicable: 0,
        approval_eligible: 1,
        approval_blocked_count: 0,
        source_warning_count: 0,
        machine_failed_count: 0,
        runnable: 1,
        release_ready_count: 0,
      },
      products: {
        total: 1,
        release_ready_count: 0,
        pending_attention: 1,
        rejected_attention: 0,
        source_warning_count: 0,
        approval_blocked_count: 0,
        machine_failed_count: 0,
      },
    },
    history: { configured: false, batches: [] },
    release: { release_manifests: [], publication_receipts: [] },
    items: [item()],
    ...overrides,
  };
}

function comparison() {
  return {
    status: "matched",
    source_fingerprint: SHA,
    payload_fingerprint: SHA,
    source: { title: "Fixture" },
    payload: { title: "Fixture" },
    diff: null,
  };
}

function evidence(overrides = {}) {
  return {
    schema_version: "1.0",
    generated_at: "2026-08-03T12:45:00Z",
    batch_id: "20260803T120000Z-deadbeef",
    item_id: "zh-cn/fixture",
    manifest_revision: 4,
    item: {
      language: "zh-cn",
      resource_key: "fixture",
      product_key: "fixture",
      page_model: "FlexibleContentPage",
      strategy: "region_filter",
      slug: "fixture",
      source_url: "https://example.test/fixture",
    },
    status: item().status,
    artifacts: {
      payload: artifact("outputs/zh-cn/pricing/fixture.json"),
      validation: artifact("validation/zh-cn/pricing/fixture.validation.json"),
      sampling_plan: artifact("validation/zh-cn/pricing/fixture.sampling-plan.json"),
      sampled_content_evidence: artifact("validation/zh-cn/pricing/fixture.sampled-content-evidence.json"),
      current_review_decision: null,
    },
    bindings: item().bindings,
    coverage: {
      mode: "stratified_sample",
      universe_count: 2,
      selected_count: 1,
      untested_count: 1,
      seed: SHA,
      strata: [SHA],
      selected_state_ids: [STATE],
      assurance: "sampled_state_content_consistency",
    },
    validation_summary: {
      status: "passed",
      evidence_sha256: SHA,
      errors: [],
      warnings: [],
      approval_preconditions: {},
    },
    source_quality_findings: [],
    machine_evidence: {
      page_global_comparison: {
        status: "matched",
        source_fingerprint: SHA,
        payload_fingerprint: SHA,
        diff_reference: null,
      },
      full_content_comparison: null,
      samples: [],
    },
    inspection: {
      mode: "interactive",
      allowed_state_ids: [STATE],
      state_universe: [{ state_id: STATE, criteria: [["region", "east"]] }],
    },
    manual_preview: {
      status: "available",
      error: null,
      page_global: comparison(),
      full_content: null,
      states: [
        {
          state_id: STATE,
          criteria: [["region", "east"]],
          machine_selected: true,
          comparison: comparison(),
        },
      ],
    },
    decisions: { current: null, history: [] },
    ...overrides,
  };
}

function independentFidelity(overrides = {}) {
  return {
    schema_version: "1.0",
    batch_id: "20260803T120000Z-deadbeef",
    item_id: "zh-cn/fixture",
    status: "failed",
    evidence_identity: {
      basis_id: "fixture-basis",
      path: "runs/20260803T120000Z-deadbeef/independent-fidelity/zh-cn/pricing/fixture/evidence.json",
      artifact_sha256: SHA,
      semantic_sha256: SHA,
      producer_commit: "c".repeat(40),
    },
    l3b: {
      claim: "independent_source_content_fidelity",
      verdict: "failed",
      coverage: { required: 1, completed: 1, passed: 0, failed: 1, blocked: 0 },
      reason: "Canonical Evidence contains failed scope results.",
      claim_limitations: ["Does not prove localization quality."],
    },
    scopes: [{
      scope_key: "full_content",
      scope_kind: "full_content",
      criteria: [],
      source_locator: {
        kind: "support_main_content",
        selector: "div.pure-content h2:first-of-type",
        boundary: "first_h2_through_parent_end_excluding_ui_nodes",
      },
      payload_locator: "mainContent",
      expected_group_name: null,
      verdict: "failed",
      source: "<h2>trusted source text</h2>",
      expected: "<h2>expected text</h2>",
      payload: "<script>alert('must stay text')</script>",
      diff: "--- expected\n+++ payload",
      applied_transform_rule_ids: ["support-url-resolution-v1"],
      retained_table_ids: [],
      removed_table_ids: [],
      mismatches: [{
        code: "content_mismatch",
        dimension: "visible_text",
        expected_sha256: SHA,
        actual_sha256: SHA,
        message: "visible_text comparison differs",
      }],
      blocking_errors: [],
      reason: "visible_text: visible_text comparison differs",
    }],
    ...overrides,
  };
}

test("review workbench projection boundary accepts canonical payload and rejects unknown item fields", () => {
  assert.doesNotThrow(() => assertWorkbenchProjection(projection()));

  const malformed = projection();
  malformed.items[0].unexpected = true;
  assert.throws(
    () => assertWorkbenchProjection(malformed),
    /\$\.items\[0\]\.unexpected/,
  );
});

test("review item evidence boundary accepts escaped comparison data and rejects malformed hashes", () => {
  assert.doesNotThrow(() => assertItemEvidence(evidence()));

  const malformed = evidence();
  malformed.manual_preview.states[0].comparison.payload_fingerprint = "A".repeat(64);
  assert.throws(
    () => assertItemEvidence(malformed),
    /\$\.manual_preview\.states\[0\]\.comparison\.payload_fingerprint/,
  );
});

test("independent fidelity boundary distinguishes negative, missing, and invalid evidence", () => {
  assert.doesNotThrow(() => assertIndependentFidelityView(independentFidelity()));
  assert.doesNotThrow(() => assertIndependentFidelityView(independentFidelity({
    status: "not_recorded",
    evidence_identity: null,
    l3b: {
      claim: "independent_source_content_fidelity",
      verdict: "not_recorded",
      coverage: null,
      reason: "No canonical Evidence bundle is recorded.",
      claim_limitations: [],
    },
    scopes: [],
  })));

  const malformed = independentFidelity();
  malformed.l3b.verdict = "passed";
  assert.throws(
    () => assertIndependentFidelityView(malformed),
    /\$\.l3b\.verdict/,
  );
});

test("L3b fragments are rendered as React text without raw HTML sinks", async () => {
  const source = await readFile(
    new URL("../app/review/ReviewWorkbench.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /<pre>\{scope\.source\}<\/pre>/);
  assert.match(source, /<pre>\{scope\.expected\}<\/pre>/);
  assert.match(source, /<pre>\{scope\.payload\}<\/pre>/);
  assert.match(source, /<pre>\{scope\.diff \|\|/);
  assert.match(source, /L3a Evidence/);
  assert.match(source, /L3b Evidence/);
  assert.match(source, /validation_summary\.evidence_sha256/);
  assert.doesNotMatch(source, /dangerouslySetInnerHTML|<iframe/i);
});

test("L3a claim label comes from the validation Evidence assurance", () => {
  assert.equal(
    l3aClaimLabel({ assurance: "sampled_state_content_consistency" }),
    "sampled_state_content_consistency",
  );
  assert.equal(l3aClaimLabel({}), "sampled_state_content_consistency");
});

test("review filters keep formal approval separate from capability dashboard filters", () => {
  const approved = item({
    status: { ...item().status, review: "approved" },
    release_ready: true,
    source_warning: false,
    approval_blocked: false,
    machine_failed: false,
    release_eligibility: { eligible: true, blockers: [] },
  });
  const rejected = item({
    item_id: "en-us/fixture",
    language: "en-us",
    status: { ...item().status, review: "rejected", evidence_binding: "stale" },
  });
  const result = filterReviewItems([item(), approved, rejected], {
    ...defaultReviewFilters,
    review: "all",
    binding: "bound",
    release: "ready",
  });

  assert.deepEqual(result, [approved]);
});

test("source filters distinguish warning, approval blocked, and clear", () => {
  const warning = item({
    source_warning: true,
    source_quality_findings: [{
      code: "SOURCE_CHARSET_DECLARATION_NOT_UTF8",
      message: "advisory",
      path: "$.meta",
      classification: "advisory",
    }],
  });
  const blocked = item({
    item_id: "en-us/blocked",
    language: "en-us",
    approval_blocked: true,
    approval_blockers: [{ code: "approval_blocking_source_quality_finding", message: "blocked" }],
  });

  assert.deepEqual(filterReviewItems([item(), warning, blocked], {
    ...defaultReviewFilters,
    review: "all",
    source: "warning",
  }), [warning]);
  assert.deepEqual(filterReviewItems([item(), warning, blocked], {
    ...defaultReviewFilters,
    review: "all",
    source: "approval_blocked",
  }), [blocked]);
  assert.deepEqual(filterReviewItems([item(), warning, blocked], {
    ...defaultReviewFilters,
    review: "all",
    source: "clear",
  }), [item()]);
});

test("capability ledger remains static and local workbench adds no API routes", async () => {
  const [dashboardSource, appEntries] = await Promise.all([
    readFile(new URL("../app/Dashboard.tsx", import.meta.url), "utf8"),
    readdir(new URL("../app", import.meta.url)),
  ]);

  assert.doesNotMatch(dashboardSource, /approved|approval|审批|批准/i);
  assert.ok(appEntries.includes("review"));
  assert.ok(!appEntries.includes("api"));
});
