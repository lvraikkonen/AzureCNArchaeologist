import assert from "node:assert/strict";
import test from "node:test";

import {
  canSubmitDecision,
  filterReviewProducts,
  parseWorkbenchConnection,
} from "../app/review-model.ts";

test("bridge token is read from the URL fragment", () => {
  assert.deepEqual(
    parseWorkbenchConnection("#bridge=http://127.0.0.1:9000&token=local-token"),
    {
      bridgeUrl: "http://127.0.0.1:9000",
      token: "local-token",
      suppliedByFragment: true,
    },
  );
});

test("an external bridge address is rejected before its token can be sent", () => {
  assert.deepEqual(
    parseWorkbenchConnection("#bridge=https://outside.example/review&token=secret"),
    {
      bridgeUrl: "http://127.0.0.1:8765",
      token: null,
      suppliedByFragment: false,
    },
  );
});

test("product filters combine decision, strategy and readable search", () => {
  const products = [
    {
      product_key: "api-management",
      display_name: "API Management",
      page_model: "FlexibleContentPage",
      semantic_strategy: "region_filter",
      status: "pending",
      reviewer: null,
      decision_path: null,
      languages: [],
    },
    {
      product_key: "icp-new",
      display_name: "ICP New",
      page_model: "SupportArticlePage",
      semantic_strategy: "support_article",
      status: "approved",
      reviewer: "审核人",
      decision_path: "decision.json",
      languages: [],
    },
  ];
  assert.deepEqual(
    filterReviewProducts(products, {
      query: "API",
      status: "pending",
      strategy: "region_filter",
    }).map((product) => product.product_key),
    ["api-management"],
  );
});

test("approval requires both languages and every material", () => {
  const base = {
    reviewer: "审核人",
    decision: "approved",
    notes: "已检查",
    inspectedLanguages: ["zh-cn", "en-us"],
    inspectedMaterials: ["frozen-html", "payload", "l3a-report", "l3b-report"],
  };
  assert.equal(canSubmitDecision(base), true);
  assert.equal(
    canSubmitDecision({ ...base, inspectedLanguages: ["zh-cn"] }),
    false,
  );
});
