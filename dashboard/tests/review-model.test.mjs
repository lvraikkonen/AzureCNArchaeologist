import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";

import {
  assertItemEvidence,
  assertWorkbenchProjection,
  defaultReviewFilters,
  filterReviewItems,
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
        approval_blocked: 0,
        source_blocked: 0,
        runnable: 1,
        release_ready: 0,
      },
      products: {
        total: 1,
        release_ready: 0,
        pending_attention: 1,
        rejected_attention: 0,
        source_blocked: 0,
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

test("review filters keep formal approval separate from capability dashboard filters", () => {
  const approved = item({
    status: { ...item().status, review: "approved" },
    release_ready: true,
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

test("capability ledger remains static and local workbench adds no API routes", async () => {
  const [dashboardSource, appEntries] = await Promise.all([
    readFile(new URL("../app/Dashboard.tsx", import.meta.url), "utf8"),
    readdir(new URL("../app", import.meta.url)),
  ]);

  assert.doesNotMatch(dashboardSource, /approved|approval|审批|批准/i);
  assert.ok(appEntries.includes("review"));
  assert.ok(!appEntries.includes("api"));
});
