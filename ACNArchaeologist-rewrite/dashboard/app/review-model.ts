export type ReviewLanguage = "zh-cn" | "en-us";
export type ReviewDecision = "approved" | "rejected";
export type ReviewStatus = ReviewDecision | "pending";
export type ComparisonStatus = "matched" | "mismatched";

export interface ReviewLanguageSummary {
  language: ReviewLanguage;
  l3a_status: string;
  l3b_status: string;
  comparison_count: number;
}

export interface ReviewProduct {
  product_key: string;
  display_name: string;
  page_model: string;
  semantic_strategy: string;
  status: ReviewStatus;
  reviewer: string | null;
  decision_path: string | null;
  languages: ReviewLanguageSummary[];
}

export interface ReviewProjection {
  schema_version: "1.0";
  review_id: string;
  run_name: string;
  batch_kind: string;
  incremental_run_name: string | null;
  review_directory: string;
  instructions: string[];
  summary: {
    queued_products: number;
    queued_items: number;
    approved_products: number;
    rejected_products: number;
    pending_products: number;
    not_queued_items: number;
  };
  products: ReviewProduct[];
  not_queued_items: { item_id: string; reason: string }[];
}

export interface ReviewComparison {
  comparison_key: string;
  payload_path: string;
  label: string;
  source_boundary: string;
  kind: "html" | "value";
  status: ComparisonStatus;
  source: unknown;
  payload: unknown;
  difference: unknown;
}

export interface ReviewLanguageEvidence {
  language: ReviewLanguage;
  paths: {
    frozen_html: string;
    payload: string;
    l3a_report: string;
    l3b_report: string;
  };
  l3a: Record<string, unknown>;
  l3b: Record<string, unknown>;
  comparisons: ReviewComparison[];
  summary: {
    comparisons: number;
    matched: number;
    mismatched: number;
  };
}

export interface ProductEvidence {
  schema_version: "1.0";
  review_id: string;
  run_name: string;
  batch_kind: string;
  incremental_run_name: string | null;
  product: Omit<ReviewProduct, "languages">;
  evidence_method: string;
  languages: ReviewLanguageEvidence[];
}

export interface ReviewFilters {
  query: string;
  status: "all" | ReviewStatus;
  strategy: string;
}

export interface WorkbenchConnection {
  bridgeUrl: string;
  token: string | null;
  suppliedByFragment: boolean;
}

export const reviewLanguages: readonly ReviewLanguage[] = ["zh-cn", "en-us"];
export const reviewMaterials = [
  ["frozen-html", "Frozen HTML"],
  ["payload", "Business Payload"],
  ["l3a-report", "L3a 报告"],
  ["l3b-report", "L3b 报告"],
] as const;

export function parseWorkbenchConnection(
  fragmentText: string,
  fallbackBridge = "http://127.0.0.1:8765",
): WorkbenchConnection {
  const fragment = new URLSearchParams(fragmentText.replace(/^#/, ""));
  const suppliedBridge = fragment.get("bridge");
  const safeSuppliedBridge = suppliedBridge
    ? validatedLocalBridgeUrl(suppliedBridge)
    : null;
  const bridgeUrl =
    safeSuppliedBridge ??
    validatedLocalBridgeUrl(fallbackBridge) ??
    "http://127.0.0.1:8765";
  return {
    bridgeUrl,
    token: suppliedBridge && !safeSuppliedBridge ? null : fragment.get("token"),
    suppliedByFragment: Boolean(safeSuppliedBridge && fragment.get("token")),
  };
}

function validatedLocalBridgeUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    const safe =
      parsed.protocol === "http:" &&
      ["127.0.0.1", "localhost"].includes(parsed.hostname) &&
      parsed.username === "" &&
      parsed.password === "" &&
      parsed.pathname === "/" &&
      parsed.search === "" &&
      !value.includes("#");
    if (safe) return parsed.origin;
  } catch {
    // The fixed local fallback below is deliberately not inferred.
  }
  return null;
}

export function filterReviewProducts(
  products: ReviewProduct[],
  filters: ReviewFilters,
): ReviewProduct[] {
  const query = filters.query.trim().toLocaleLowerCase("zh-CN");
  return products.filter((product) => {
    if (filters.status !== "all" && product.status !== filters.status) return false;
    if (filters.strategy !== "all" && product.semantic_strategy !== filters.strategy) return false;
    if (!query) return true;
    return `${product.product_key} ${product.display_name}`
      .toLocaleLowerCase("zh-CN")
      .includes(query);
  });
}

export function canSubmitDecision(input: {
  reviewer: string;
  decision: ReviewDecision;
  notes: string;
  inspectedLanguages: ReviewLanguage[];
  inspectedMaterials: string[];
}): boolean {
  if (!input.reviewer.trim() || !input.notes.trim()) return false;
  if (input.inspectedLanguages.length === 0 || input.inspectedMaterials.length === 0) return false;
  if (input.decision === "approved") {
    return (
      reviewLanguages.every((language) => input.inspectedLanguages.includes(language)) &&
      reviewMaterials.every(([material]) => input.inspectedMaterials.includes(material))
    );
  }
  return true;
}

function objectValue(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("人工审核台响应必须是 JSON 对象。");
  }
  return value as Record<string, unknown>;
}

export function assertReviewProjection(value: unknown): asserts value is ReviewProjection {
  const root = objectValue(value);
  if (
    root.schema_version !== "1.0" ||
    typeof root.review_id !== "string" ||
    typeof root.batch_kind !== "string" ||
    !(
      root.incremental_run_name === null ||
      typeof root.incremental_run_name === "string"
    )
  ) {
    throw new Error("人工审核台的审核清单版本无效。");
  }
  if (!Array.isArray(root.products) || !Array.isArray(root.not_queued_items)) {
    throw new Error("人工审核台的审核清单缺少产品或未入队处理项。");
  }
  root.products.forEach((candidate) => {
    const product = objectValue(candidate);
    if (
      typeof product.product_key !== "string" ||
      !["pending", "approved", "rejected"].includes(String(product.status)) ||
      !Array.isArray(product.languages)
    ) {
      throw new Error("人工审核台的产品记录无效。");
    }
  });
}

export function assertProductEvidence(value: unknown): asserts value is ProductEvidence {
  const root = objectValue(value);
  if (
    root.schema_version !== "1.0" ||
    typeof root.batch_kind !== "string" ||
    !(
      root.incremental_run_name === null ||
      typeof root.incremental_run_name === "string"
    ) ||
    !Array.isArray(root.languages)
  ) {
    throw new Error("人工审核台的产品证据版本无效。");
  }
  if (root.languages.length !== 2) {
    throw new Error("人工审核台的产品证据必须完整包含中英文。");
  }
  root.languages.forEach((candidate) => {
    const language = objectValue(candidate);
    if (!reviewLanguages.includes(language.language as ReviewLanguage)) {
      throw new Error("人工审核台的产品证据包含未知语言。");
    }
    if (!Array.isArray(language.comparisons)) {
      throw new Error("人工审核台的产品证据缺少并排比较项。");
    }
  });
}
