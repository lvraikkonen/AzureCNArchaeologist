export type LanguageCode = "zh-cn" | "en-us";
export type CapabilityStatus = "supported" | "known_unsupported";
export type MachineLanguageStatus = "pass" | "fail" | "not_applicable";
export type MachineOutcome =
  | "bilingual_pass"
  | "single_language_pass"
  | "bilingual_fail"
  | "known_unsupported";
export type ManualVerdict = "pending" | "passed" | "failed" | "findings";
export type ManualOutcome =
  | "passed"
  | "failed"
  | "findings"
  | "pending"
  | "stale"
  | "not_applicable";
export type BindingStatus = "bound" | "legacy_unbound" | "stale";
export type BindingFacet =
  | BindingStatus
  | "unrecorded"
  | "not_applicable";
export type ManualLanguageDisplayStatus =
  | ManualVerdict
  | "not_applicable";

export interface Finding {
  code?: string;
  area?: string;
  summary?: string;
  details?: string;
  status?: string;
  [key: string]: unknown;
}

export interface MachineDiagnostic {
  code?: string;
  stage?: string;
  path?: string;
  message?: string;
  [key: string]: unknown;
}

export interface MachineLanguageEvidence {
  status: MachineLanguageStatus;
  execution: string | null;
  validation: string | null;
  source_path: string | null;
  source_sha256: string | null;
  payload_path: string | null;
  payload_sha256: string | null;
  content_group_count: number | null;
  error: MachineDiagnostic | null;
  validation_errors: MachineDiagnostic[];
  validation_warnings: MachineDiagnostic[];
}

export interface ManualLanguageInspection {
  is_applicable: boolean;
  verdict: ManualVerdict;
  binding_status: BindingStatus | null;
  reviewer: string | null;
  reviewed_at: string | null;
  source_sha256: string | null;
  payload_sha256: string | null;
  notes: string[];
  findings: Finding[];
}

export interface ProductLanguageProjection {
  machine: MachineLanguageEvidence;
  manual: ManualLanguageInspection;
}

export interface ProductProjection {
  product_key: string;
  display_name: string;
  slug: string;
  catalog_categories: string[];
  url: string;
  semantic_strategy: string | null;
  capability_status: CapabilityStatus;
  unsupported_reason: string | null;
  machine_outcome: MachineOutcome;
  manual_outcome: ManualOutcome;
  binding_status: BindingStatus | null;
  languages: Record<LanguageCode, ProductLanguageProjection>;
  unscoped_findings: Finding[];
  manual_notes: string[];
  raw_legacy: unknown;
}

export interface DashboardProjection {
  schema_version: string;
  projection_id: string;
  generated_at: string;
  data_date: string;
  source: {
    scope: {
      id: string;
      path: string;
      sha256: string;
    };
    machine_evidence: {
      kind: string;
      schema_version: string;
      path: string;
      sha256: string;
      report_id: string;
      formal_batch_created: boolean;
    };
    manual_inspection: {
      id: string;
      path: string;
      sha256: string;
    };
  };
  summary: DashboardSummary;
  attention: {
    findings_product_keys: string[];
    pending_product_keys: string[];
    stale_product_keys: string[];
  };
  products: ProductProjection[];
}

export interface DashboardSummary {
  scope: {
    total: number;
    supported: number;
    known_unsupported: number;
  };
  machine: {
    bilingual_pass: number;
    single_language_pass: number;
    bilingual_fail: number;
    zh_cn_pass: number;
    zh_cn_fail: number;
    en_us_pass: number;
    en_us_fail: number;
    passed_language_items: number;
  };
  manual: {
    reviewable_products: number;
    clear_conclusions: number;
    passed_products: number;
    failed_products: number;
    findings_products: number;
    pending_products: number;
  };
  binding: {
    bound: number;
    legacy_unbound: number;
    stale: number;
  };
}

export function getManualLanguageDisplay(
  inspection: ManualLanguageInspection,
): { status: ManualLanguageDisplayStatus; label: string } {
  if (!inspection.is_applicable) {
    return { status: "not_applicable", label: "不适用" };
  }

  const labels: Record<ManualVerdict, string> = {
    passed: "通过",
    failed: "失败",
    findings: "有发现",
    pending: "待检查",
  };
  return {
    status: inspection.verdict,
    label: labels[inspection.verdict],
  };
}

export function getBindingFacet(
  source:
    | Pick<ProductProjection, "binding_status" | "manual_outcome">
    | Pick<ManualLanguageInspection, "binding_status" | "is_applicable">,
): BindingFacet {
  if (source.binding_status) return source.binding_status;
  if ("is_applicable" in source) {
    return source.is_applicable ? "unrecorded" : "not_applicable";
  }
  return source.manual_outcome === "not_applicable"
    ? "not_applicable"
    : "unrecorded";
}

export function countOpenFindings(product: ProductProjection): number {
  const allFindings = [
    ...product.unscoped_findings,
    ...product.languages["zh-cn"].manual.findings,
    ...product.languages["en-us"].manual.findings,
  ];
  return allFindings.filter((finding) => finding.status !== "resolved").length;
}

export function formatMachineDiagnostic(
  diagnostic: MachineDiagnostic,
): string {
  const prefix = diagnostic.code ? `[${diagnostic.code}] ` : "";
  const message =
    diagnostic.message ??
    diagnostic.stage ??
    diagnostic.path ??
    JSON.stringify(diagnostic);
  const location = diagnostic.path ?? diagnostic.stage;
  return `${prefix}${message}${location && location !== message ? ` · ${location}` : ""}`;
}

type UnknownRecord = Record<string, unknown>;
const SHA256 = /^[0-9a-f]{64}$/;

function projectionError(path: string, expectation: string): never {
  throw new TypeError(
    `Invalid capability dashboard projection at ${path}: ${expectation}`,
  );
}

function requireRecord(value: unknown, path: string): UnknownRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return projectionError(path, "expected an object");
  }
  return value as UnknownRecord;
}

function requireStringValue(
  value: unknown,
  path: string,
  nonEmpty = false,
): string {
  if (
    typeof value !== "string" ||
    (nonEmpty && value.length === 0)
  ) {
    projectionError(
      path,
      nonEmpty ? "expected a non-empty string" : "expected a string",
    );
  }
  return value;
}

function requireRecordString(
  record: UnknownRecord,
  key: string,
  path: string,
  nonEmpty = false,
): string {
  return requireStringValue(record[key], `${path}.${key}`, nonEmpty);
}

function requireNullableString(value: unknown, path: string): void {
  if (value !== null && typeof value !== "string") {
    projectionError(path, "expected a string or null");
  }
}

function requireBoolean(value: unknown, path: string): void {
  if (typeof value !== "boolean") {
    projectionError(path, "expected a boolean");
  }
}

function requireNonNegativeInteger(value: unknown, path: string): number {
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    value < 0
  ) {
    projectionError(path, "expected a non-negative integer");
  }
  return value;
}

function requireNullableNonNegativeInteger(
  value: unknown,
  path: string,
): void {
  if (value !== null) requireNonNegativeInteger(value, path);
}

function requireEnum(
  value: unknown,
  allowed: readonly string[],
  path: string,
): void {
  if (typeof value !== "string" || !allowed.includes(value)) {
    projectionError(path, `expected one of ${allowed.join(", ")}`);
  }
}

function requireNullableEnum(
  value: unknown,
  allowed: readonly string[],
  path: string,
): void {
  if (value !== null) requireEnum(value, allowed, path);
}

function requireSha256(value: unknown, path: string): void {
  if (typeof value !== "string" || !SHA256.test(value)) {
    projectionError(path, "expected a lowercase SHA-256 string");
  }
}

function requireNullableSha256(value: unknown, path: string): void {
  if (value !== null) requireSha256(value, path);
}

function requireArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    projectionError(path, "expected an array");
  }
  return value;
}

function requireStringArray(value: unknown, path: string): void {
  requireArray(value, path).forEach((item, index) => {
    requireStringValue(item, `${path}[${index}]`);
  });
}

function requireIntegerFields(
  record: UnknownRecord,
  fields: readonly string[],
  path: string,
): void {
  for (const field of fields) {
    requireNonNegativeInteger(record[field], `${path}.${field}`);
  }
}

function validateArtifact(value: unknown, path: string): void {
  const artifact = requireRecord(value, path);
  requireRecordString(artifact, "id", path, true);
  requireRecordString(artifact, "path", path, true);
  requireSha256(artifact.sha256, `${path}.sha256`);
}

function validateFinding(value: unknown, path: string): void {
  const finding = requireRecord(value, path);
  requireRecordString(finding, "code", path);
  requireRecordString(finding, "area", path);
  requireRecordString(finding, "summary", path);
  requireEnum(finding.status, ["open", "resolved"], `${path}.status`);
}

function validateFindingArray(value: unknown, path: string): void {
  requireArray(value, path).forEach((finding, index) => {
    validateFinding(finding, `${path}[${index}]`);
  });
}

function validateMachineError(value: unknown, path: string): void {
  const error = requireRecord(value, path);
  requireRecordString(error, "code", path);
  requireRecordString(error, "stage", path);
  requireRecordString(error, "message", path);
}

function validateMachineIssue(value: unknown, path: string): void {
  const issue = requireRecord(value, path);
  requireRecordString(issue, "code", path);
  requireRecordString(issue, "path", path);
  requireRecordString(issue, "message", path);
}

function validateMachineIssueArray(value: unknown, path: string): void {
  requireArray(value, path).forEach((issue, index) => {
    validateMachineIssue(issue, `${path}[${index}]`);
  });
}

function validateRawLegacy(value: unknown, path: string): void {
  if (value === null) return;
  const rawLegacy = requireRecord(value, path);
  for (const field of [
    "manual_status_column",
    "manual_evidence_column",
    "misplaced_machine_note",
  ]) {
    requireRecordString(rawLegacy, field, path);
  }
}

export function assertDashboardProjection(
  value: unknown,
): asserts value is DashboardProjection {
  const root = requireRecord(value, "$");
  for (const key of [
    "schema_version",
    "projection_id",
    "generated_at",
    "data_date",
  ]) {
    requireRecordString(root, key, "$", true);
  }

  const source = requireRecord(root.source, "$.source");
  validateArtifact(source.scope, "$.source.scope");
  const machineEvidence = requireRecord(
    source.machine_evidence,
    "$.source.machine_evidence",
  );
  requireEnum(
    machineEvidence.kind,
    ["step3_probe"],
    "$.source.machine_evidence.kind",
  );
  requireEnum(
    machineEvidence.schema_version,
    ["1.0"],
    "$.source.machine_evidence.schema_version",
  );
  requireRecordString(
    machineEvidence,
    "path",
    "$.source.machine_evidence",
    true,
  );
  requireSha256(
    machineEvidence.sha256,
    "$.source.machine_evidence.sha256",
  );
  requireRecordString(
    machineEvidence,
    "report_id",
    "$.source.machine_evidence",
    true,
  );
  requireBoolean(
    machineEvidence.formal_batch_created,
    "$.source.machine_evidence.formal_batch_created",
  );
  validateArtifact(
    source.manual_inspection,
    "$.source.manual_inspection",
  );

  const summary = requireRecord(root.summary, "$.summary");
  const scopeSummary = requireRecord(summary.scope, "$.summary.scope");
  requireIntegerFields(
    scopeSummary,
    ["total", "supported", "known_unsupported"],
    "$.summary.scope",
  );
  const machineSummary = requireRecord(
    summary.machine,
    "$.summary.machine",
  );
  requireIntegerFields(
    machineSummary,
    [
      "bilingual_pass",
      "single_language_pass",
      "bilingual_fail",
      "zh_cn_pass",
      "zh_cn_fail",
      "en_us_pass",
      "en_us_fail",
      "passed_language_items",
    ],
    "$.summary.machine",
  );
  const manualSummary = requireRecord(summary.manual, "$.summary.manual");
  requireIntegerFields(
    manualSummary,
    [
      "reviewable_products",
      "clear_conclusions",
      "passed_products",
      "failed_products",
      "findings_products",
      "pending_products",
    ],
    "$.summary.manual",
  );
  const bindingSummary = requireRecord(summary.binding, "$.summary.binding");
  requireIntegerFields(
    bindingSummary,
    ["bound", "legacy_unbound", "stale"],
    "$.summary.binding",
  );

  const attention = requireRecord(root.attention, "$.attention");
  for (const field of [
    "findings_product_keys",
    "pending_product_keys",
    "stale_product_keys",
  ]) {
    requireStringArray(attention[field], `$.attention.${field}`);
  }

  const products = requireArray(root.products, "$.products");
  if (products.length !== scopeSummary.total) {
    projectionError(
      "$.products",
      `expected ${scopeSummary.total} products from summary.scope.total`,
    );
  }

  const productKeys = new Set<string>();
  products.forEach((entry, index) => {
    const path = `$.products[${index}]`;
    const product = requireRecord(entry, path);
    const productKey = requireRecordString(product, "product_key", path);
    requireRecordString(product, "display_name", path);
    requireRecordString(product, "slug", path);
    requireStringArray(
      product.catalog_categories,
      `${path}.catalog_categories`,
    );
    const url = requireRecordString(product, "url", path);
    try {
      new URL(url);
    } catch {
      projectionError(`${path}.url`, "expected an absolute URL");
    }
    requireNullableEnum(
      product.semantic_strategy,
      ["simple_static", "region_filter", "complex"],
      `${path}.semantic_strategy`,
    );
    requireEnum(
      product.capability_status,
      ["supported", "known_unsupported"],
      `${path}.capability_status`,
    );
    requireNullableString(product.unsupported_reason, `${path}.unsupported_reason`);
    requireEnum(
      product.machine_outcome,
      [
        "bilingual_pass",
        "single_language_pass",
        "bilingual_fail",
        "known_unsupported",
      ],
      `${path}.machine_outcome`,
    );
    requireEnum(
      product.manual_outcome,
      [
        "passed",
        "failed",
        "findings",
        "pending",
        "stale",
        "not_applicable",
      ],
      `${path}.manual_outcome`,
    );
    requireNullableEnum(
      product.binding_status,
      ["bound", "legacy_unbound", "stale"],
      `${path}.binding_status`,
    );
    if (productKeys.has(productKey)) {
      projectionError(`${path}.product_key`, `duplicate key ${productKey}`);
    }
    productKeys.add(productKey);

    const languages = requireRecord(product.languages, `${path}.languages`);
    for (const language of ["zh-cn", "en-us"] as const) {
      const languageRecord = requireRecord(
        languages[language],
        `${path}.languages.${language}`,
      );
      const machine = requireRecord(
        languageRecord.machine,
        `${path}.languages.${language}.machine`,
      );
      const machinePath = `${path}.languages.${language}.machine`;
      requireEnum(
        machine.status,
        ["pass", "fail", "not_applicable"],
        `${machinePath}.status`,
      );
      requireRecordString(machine, "execution", machinePath);
      requireRecordString(machine, "validation", machinePath);
      requireNullableString(machine.source_path, `${machinePath}.source_path`);
      requireNullableSha256(
        machine.source_sha256,
        `${machinePath}.source_sha256`,
      );
      requireNullableString(machine.payload_path, `${machinePath}.payload_path`);
      requireNullableSha256(
        machine.payload_sha256,
        `${machinePath}.payload_sha256`,
      );
      requireNullableNonNegativeInteger(
        machine.content_group_count,
        `${machinePath}.content_group_count`,
      );
      if (machine.error !== null) {
        validateMachineError(machine.error, `${machinePath}.error`);
      }
      validateMachineIssueArray(
        machine.validation_errors,
        `${machinePath}.validation_errors`,
      );
      validateMachineIssueArray(
        machine.validation_warnings,
        `${machinePath}.validation_warnings`,
      );

      const manual = requireRecord(
        languageRecord.manual,
        `${path}.languages.${language}.manual`,
      );
      const manualPath = `${path}.languages.${language}.manual`;
      requireBoolean(manual.is_applicable, `${manualPath}.is_applicable`);
      requireEnum(
        manual.verdict,
        ["pending", "passed", "failed", "findings"],
        `${manualPath}.verdict`,
      );
      requireNullableEnum(
        manual.binding_status,
        ["bound", "legacy_unbound", "stale"],
        `${manualPath}.binding_status`,
      );
      requireNullableString(manual.reviewer, `${manualPath}.reviewer`);
      requireNullableString(manual.reviewed_at, `${manualPath}.reviewed_at`);
      requireNullableSha256(
        manual.source_sha256,
        `${manualPath}.source_sha256`,
      );
      requireNullableSha256(
        manual.payload_sha256,
        `${manualPath}.payload_sha256`,
      );
      requireStringArray(manual.notes, `${manualPath}.notes`);
      validateFindingArray(manual.findings, `${manualPath}.findings`);
    }
    validateFindingArray(
      product.unscoped_findings,
      `${path}.unscoped_findings`,
    );
    requireStringArray(product.manual_notes, `${path}.manual_notes`);
    validateRawLegacy(product.raw_legacy, `${path}.raw_legacy`);
  });
}

export type ProductSort =
  | "name_asc"
  | "name_desc"
  | "attention"
  | "category"
  | "product_key";

export interface ProductFilters {
  query: string;
  category: string;
  strategy: string;
  machine: string;
  manual: string;
  language: "all" | LanguageCode;
  binding: string;
  sort: ProductSort;
}

export const defaultFilters: ProductFilters = {
  query: "",
  category: "all",
  strategy: "all",
  machine: "all",
  manual: "all",
  language: "all",
  binding: "all",
  sort: "name_asc",
};

const attentionRank: Record<ManualOutcome, number> = {
  stale: 0,
  findings: 1,
  pending: 2,
  failed: 3,
  passed: 4,
  not_applicable: 5,
};

export function deriveSummary(
  products: ProductProjection[],
): DashboardSummary {
  const summary: DashboardSummary = {
    scope: {
      total: products.length,
      supported: 0,
      known_unsupported: 0,
    },
    machine: {
      bilingual_pass: 0,
      single_language_pass: 0,
      bilingual_fail: 0,
      zh_cn_pass: 0,
      zh_cn_fail: 0,
      en_us_pass: 0,
      en_us_fail: 0,
      passed_language_items: 0,
    },
    manual: {
      reviewable_products: 0,
      clear_conclusions: 0,
      passed_products: 0,
      failed_products: 0,
      findings_products: 0,
      pending_products: 0,
    },
    binding: {
      bound: 0,
      legacy_unbound: 0,
      stale: 0,
    },
  };

  for (const product of products) {
    summary.scope[product.capability_status] += 1;

    if (product.machine_outcome in summary.machine) {
      const key = product.machine_outcome as
        | "bilingual_pass"
        | "single_language_pass"
        | "bilingual_fail";
      summary.machine[key] += 1;
    }

    const zhStatus = product.languages["zh-cn"].machine.status;
    const enStatus = product.languages["en-us"].machine.status;
    if (zhStatus === "pass") {
      summary.machine.zh_cn_pass += 1;
      summary.machine.passed_language_items += 1;
    } else if (zhStatus === "fail") {
      summary.machine.zh_cn_fail += 1;
    }
    if (enStatus === "pass") {
      summary.machine.en_us_pass += 1;
      summary.machine.passed_language_items += 1;
    } else if (enStatus === "fail") {
      summary.machine.en_us_fail += 1;
    }

    const reviewable = zhStatus === "pass" || enStatus === "pass";
    if (reviewable) {
      summary.manual.reviewable_products += 1;
    }
    if (product.manual_outcome === "passed") {
      summary.manual.passed_products += 1;
      summary.manual.clear_conclusions += 1;
    } else if (product.manual_outcome === "failed") {
      summary.manual.failed_products += 1;
      summary.manual.clear_conclusions += 1;
    } else if (product.manual_outcome === "findings") {
      summary.manual.findings_products += 1;
    } else if (product.manual_outcome === "pending") {
      summary.manual.pending_products += 1;
    }

    if (product.binding_status) {
      summary.binding[product.binding_status] += 1;
    }
  }

  return summary;
}

export function filterAndSortProducts(
  products: ProductProjection[],
  filters: ProductFilters,
): ProductProjection[] {
  const query = filters.query.trim().toLocaleLowerCase("zh-CN");

  const filtered = products.filter((product) => {
    const searchable = [
      product.display_name,
      product.product_key,
      product.slug,
      product.url,
      ...product.catalog_categories,
    ]
      .join(" ")
      .toLocaleLowerCase("zh-CN");

    return (
      (!query || searchable.includes(query)) &&
      (filters.category === "all" ||
        product.catalog_categories.includes(filters.category)) &&
      (filters.strategy === "all" ||
        (product.semantic_strategy ?? "none") === filters.strategy) &&
      (filters.machine === "all" ||
        product.machine_outcome === filters.machine) &&
      (filters.manual === "all" ||
        product.manual_outcome === filters.manual) &&
      (filters.language === "all" ||
        product.languages[filters.language].machine.status === "pass") &&
      (filters.binding === "all" ||
        getBindingFacet(product) === filters.binding)
    );
  });

  return filtered.toSorted((left, right) => {
    if (filters.sort === "attention") {
      const rank =
        attentionRank[left.manual_outcome] -
        attentionRank[right.manual_outcome];
      if (rank !== 0) return rank;
    } else if (filters.sort === "name_desc") {
      return right.display_name.localeCompare(left.display_name, "zh-CN");
    } else if (filters.sort === "category") {
      const category = (left.catalog_categories[0] ?? "").localeCompare(
        right.catalog_categories[0] ?? "",
        "zh-CN",
      );
      if (category !== 0) return category;
    } else if (filters.sort === "product_key") {
      return left.product_key.localeCompare(right.product_key, "en");
    }

    return left.display_name.localeCompare(right.display_name, "zh-CN");
  });
}

export function getAttentionProducts(
  products: ProductProjection[],
): ProductProjection[] {
  return products
    .filter((product) =>
      ["stale", "findings", "pending"].includes(product.manual_outcome),
    )
    .toSorted((left, right) => {
      const rank =
        attentionRank[left.manual_outcome] -
        attentionRank[right.manual_outcome];
      if (rank !== 0) return rank;
      return left.display_name.localeCompare(right.display_name, "zh-CN");
    });
}

export function getProductDetail(
  products: ProductProjection[],
  productKey: string | null,
): ProductProjection | null {
  if (!productKey) return null;
  return (
    products.find((product) => product.product_key === productKey) ?? null
  );
}

export function emptyStateMessage(filters: ProductFilters): string {
  if (filters.query.trim()) {
    return `没有与“${filters.query.trim()}”匹配的产品。`;
  }
  return "当前筛选组合没有匹配的产品。";
}

export function distinctValues(
  products: ProductProjection[],
  selector: (product: ProductProjection) => string[],
): string[] {
  return Array.from(new Set(products.flatMap(selector)))
    .filter(Boolean)
    .toSorted((left, right) => left.localeCompare(right, "zh-CN"));
}
