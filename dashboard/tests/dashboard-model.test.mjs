import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  assertDashboardProjection,
  countOpenFindings,
  defaultFilters,
  deriveSummary,
  emptyStateMessage,
  filterAndSortProducts,
  formatMachineDiagnostic,
  getAttentionProducts,
  getBindingFacet,
  getManualLanguageDisplay,
  getProductDetail,
} from "../app/dashboard-model.ts";

function language(machineStatus, manualVerdict = "pending") {
  return {
    machine: {
      status: machineStatus,
      execution: null,
      validation: null,
      source_path: null,
      source_sha256: null,
      payload_path: null,
      payload_sha256: null,
      content_group_count: machineStatus === "pass" ? 2 : null,
      error:
        machineStatus === "fail"
          ? { code: "FIXTURE_FAILURE", message: "fixture failure" }
          : null,
      validation_errors: [],
      validation_warnings: [],
    },
    manual: {
      is_applicable: machineStatus === "pass",
      verdict: manualVerdict,
      binding_status: null,
      reviewer: null,
      reviewed_at: null,
      source_sha256: null,
      payload_sha256: null,
      notes: [],
      findings: [],
    },
  };
}

const products = [
  {
    product_key: "alpha",
    display_name: "Alpha Database",
    slug: "alpha",
    catalog_categories: ["数据库"],
    url: "https://example.test/alpha/",
    semantic_strategy: "complex",
    capability_status: "supported",
    unsupported_reason: null,
    machine_outcome: "bilingual_pass",
    manual_outcome: "passed",
    binding_status: "legacy_unbound",
    languages: {
      "zh-cn": language("pass", "passed"),
      "en-us": language("pass", "passed"),
    },
    unscoped_findings: [],
    manual_notes: [],
    raw_legacy: null,
  },
  {
    product_key: "beta",
    display_name: "Beta Network",
    slug: "beta",
    catalog_categories: ["网络"],
    url: "https://example.test/beta/",
    semantic_strategy: "region_filter",
    capability_status: "supported",
    unsupported_reason: null,
    machine_outcome: "single_language_pass",
    manual_outcome: "pending",
    binding_status: null,
    languages: {
      "zh-cn": language("fail"),
      "en-us": language("pass"),
    },
    unscoped_findings: [],
    manual_notes: [],
    raw_legacy: null,
  },
  {
    product_key: "gamma",
    display_name: "Gamma Legacy",
    slug: "gamma",
    catalog_categories: ["计算"],
    url: "https://example.test/gamma/",
    semantic_strategy: null,
    capability_status: "known_unsupported",
    unsupported_reason: "fixture",
    machine_outcome: "known_unsupported",
    manual_outcome: "not_applicable",
    binding_status: null,
    languages: {
      "zh-cn": language("not_applicable"),
      "en-us": language("not_applicable"),
    },
    unscoped_findings: [],
    manual_notes: [],
    raw_legacy: null,
  },
];

test("derives categorical summary without collapsing evidence types", () => {
  const summary = deriveSummary(products);

  assert.deepEqual(summary.scope, {
    total: 3,
    supported: 2,
    known_unsupported: 1,
  });
  assert.equal(summary.machine.bilingual_pass, 1);
  assert.equal(summary.machine.single_language_pass, 1);
  assert.equal(summary.machine.passed_language_items, 3);
  assert.equal(summary.manual.reviewable_products, 2);
  assert.equal(summary.manual.clear_conclusions, 1);
  assert.equal(summary.manual.pending_products, 1);
  assert.deepEqual(summary.binding, {
    bound: 0,
    legacy_unbound: 1,
    stale: 0,
  });
});

test("current projection summary matches product-derived categories", async () => {
  const projection = JSON.parse(
    await readFile(
      new URL("../app/generated/capability-dashboard.json", import.meta.url),
      "utf8",
    ),
  );

  assert.deepEqual(deriveSummary(projection.products), projection.summary);
});

test("runtime boundary accepts canonical projection and rejects malformed language records", async () => {
  const projection = JSON.parse(
    await readFile(
      new URL("../app/generated/capability-dashboard.json", import.meta.url),
      "utf8",
    ),
  );
  assert.doesNotThrow(() => assertDashboardProjection(projection));

  const malformed = structuredClone(projection);
  malformed.products[0].languages["zh-cn"].manual.is_applicable = "false";
  assert.throws(
    () => assertDashboardProjection(malformed),
    /Invalid capability dashboard projection at \$\.products\[0\]\.languages\.zh-cn\.manual\.is_applicable/,
  );
});

test("runtime boundary rejects malformed UI-consumed fields across the projection", async () => {
  const projection = JSON.parse(
    await readFile(
      new URL("../app/generated/capability-dashboard.json", import.meta.url),
      "utf8",
    ),
  );
  const findingProductIndex = projection.products.findIndex(
    (product) => product.unscoped_findings.length > 0,
  );
  assert.notEqual(findingProductIndex, -1);

  const cases = [
    {
      mutate(value) {
        value.summary.machine = {};
      },
      error: /\$\.summary\.machine\.bilingual_pass/,
    },
    {
      mutate(value) {
        value.source.scope.sha256 = 42;
      },
      error: /\$\.source\.scope\.sha256/,
    },
    {
      mutate(value) {
        value.products[0].url = 42;
      },
      error: /\$\.products\[0\]\.url/,
    },
    {
      mutate(value) {
        value.products[0].capability_status = "maybe_supported";
      },
      error: /\$\.products\[0\]\.capability_status/,
    },
    {
      mutate(value) {
        value.products[0].languages["zh-cn"].machine.validation_errors =
          "oops";
      },
      error:
        /\$\.products\[0\]\.languages\.zh-cn\.machine\.validation_errors/,
    },
    {
      mutate(value) {
        value.products[0].languages["zh-cn"].manual.notes = {};
      },
      error: /\$\.products\[0\]\.languages\.zh-cn\.manual\.notes/,
    },
    {
      mutate(value) {
        value.products[findingProductIndex].unscoped_findings[0].status =
          "archived";
      },
      error: new RegExp(
        `\\$\\.products\\[${findingProductIndex}\\]\\.unscoped_findings\\[0\\]\\.status`,
      ),
    },
    {
      mutate(value) {
        value.attention.pending_product_keys = [42];
      },
      error: /\$\.attention\.pending_product_keys\[0\]/,
    },
  ];

  for (const fixture of cases) {
    const malformed = structuredClone(projection);
    fixture.mutate(malformed);
    assert.throws(
      () => assertDashboardProjection(malformed),
      fixture.error,
    );
  }
});

test("combines search, category, strategy, result, language and binding filters", () => {
  const result = filterAndSortProducts(products, {
    ...defaultFilters,
    query: "database",
    category: "数据库",
    strategy: "complex",
    machine: "bilingual_pass",
    manual: "passed",
    language: "zh-cn",
    binding: "legacy_unbound",
  });

  assert.deepEqual(
    result.map((product) => product.product_key),
    ["alpha"],
  );
});

test("language facet includes only machine-passed payloads in the canonical projection", async () => {
  const projection = JSON.parse(
    await readFile(
      new URL("../app/generated/capability-dashboard.json", import.meta.url),
      "utf8",
    ),
  );
  const zhCn = filterAndSortProducts(projection.products, {
    ...defaultFilters,
    language: "zh-cn",
  });
  const enUs = filterAndSortProducts(projection.products, {
    ...defaultFilters,
    language: "en-us",
  });

  assert.equal(zhCn.length, 42);
  assert.equal(enUs.length, 44);
  assert.ok(
    zhCn.every(
      (product) => product.languages["zh-cn"].machine.status === "pass",
    ),
  );
  assert.ok(
    enUs.every(
      (product) => product.languages["en-us"].machine.status === "pass",
    ),
  );
});

test("manual applicability controls language display and binding facets", () => {
  const cosmosLikeFailedLanguage = products[1].languages["zh-cn"];
  assert.deepEqual(
    getManualLanguageDisplay(cosmosLikeFailedLanguage.manual),
    { status: "not_applicable", label: "不适用" },
  );
  assert.deepEqual(
    getManualLanguageDisplay(products[0].languages["zh-cn"].manual),
    { status: "passed", label: "通过" },
  );
  assert.equal(getBindingFacet(products[1]), "unrecorded");
  assert.equal(getBindingFacet(cosmosLikeFailedLanguage.manual), "not_applicable");
  assert.equal(getBindingFacet(products[2]), "not_applicable");
  assert.equal(getBindingFacet(products[0]), "legacy_unbound");
});

test("unrecorded binding facet identifies the two canonical pending products", async () => {
  const projection = JSON.parse(
    await readFile(
      new URL("../app/generated/capability-dashboard.json", import.meta.url),
      "utf8",
    ),
  );
  const unrecorded = filterAndSortProducts(projection.products, {
    ...defaultFilters,
    binding: "unrecorded",
  });

  assert.deepEqual(
    new Set(unrecorded.map((product) => product.product_key)),
    new Set(["cosmos-db", "synapse-analytics"]),
  );
});

test("sorts attention deterministically and exposes the same attention queue", () => {
  const withFinding = {
    ...products[0],
    product_key: "delta",
    display_name: "Delta",
    manual_outcome: "findings",
  };
  const fixture = [...products, withFinding];

  const sorted = filterAndSortProducts(fixture, {
    ...defaultFilters,
    sort: "attention",
  });
  assert.deepEqual(
    sorted.slice(0, 2).map((product) => product.manual_outcome),
    ["findings", "pending"],
  );
  assert.deepEqual(
    getAttentionProducts(fixture).map((product) => product.product_key),
    ["delta", "beta"],
  );
});

test("attention count ignores resolved findings while detail data remains intact", () => {
  const fixture = {
    ...products[0],
    unscoped_findings: [
      { code: "OPEN", summary: "open", status: "open" },
      { code: "RESOLVED", summary: "resolved", status: "resolved" },
      { code: "LEGACY", summary: "legacy without status" },
    ],
  };

  assert.equal(countOpenFindings(fixture), 2);
  assert.equal(fixture.unscoped_findings.length, 3);
});

test("resolves product detail and provides a useful empty-state message", () => {
  assert.equal(getProductDetail(products, "beta")?.display_name, "Beta Network");
  assert.equal(getProductDetail(products, "missing"), null);
  assert.equal(
    emptyStateMessage({ ...defaultFilters, query: "No Such Product" }),
    "没有与“No Such Product”匹配的产品。",
  );
  assert.equal(
    emptyStateMessage({ ...defaultFilters, category: "身份" }),
    "当前筛选组合没有匹配的产品。",
  );
});

test("formats structured machine diagnostics for readable detail evidence", () => {
  assert.equal(
    formatMachineDiagnostic({
      code: "DISPLAY_DRIFT",
      path: "$.expected_reachability",
      message: "Default display disagrees.",
    }),
    "[DISPLAY_DRIFT] Default display disagrees. · $.expected_reachability",
  );
});

test("dashboard source and generated projection avoid aggregate scores and approval language", async () => {
  const [component, projection] = await Promise.all([
    readFile(new URL("../app/Dashboard.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../app/generated/capability-dashboard.json", import.meta.url),
      "utf8",
    ),
  ]);

  assert.doesNotMatch(component, /quality[_ -]?score/i);
  assert.doesNotMatch(projection, /quality[_ -]?score/i);
  assert.doesNotMatch(component, /批准|审批|approval|approved/i);
  assert.match(component, /人工内容检查/);
});

test("starter preview and editing affordances are absent", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  const combined = `${page}\n${layout}\n${packageJson}`;
  assert.doesNotMatch(combined, /codex-preview|SkeletonPreview|react-loading-skeleton/);
  assert.doesNotMatch(combined, /drizzle|login|sign.?in|auth/i);
  assert.match(layout, /Azure 中国区产品能力追踪/);
  assert.match(layout, /\/og\.png/);
  assert.match(
    await readFile(new URL("../app/Dashboard.tsx", import.meta.url), "utf8"),
    /机器证据生成于/,
  );
});
