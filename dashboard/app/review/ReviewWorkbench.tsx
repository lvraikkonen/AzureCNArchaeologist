"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ProductEvidence,
  ReviewComparison,
  ReviewDecision,
  ReviewFilters,
  ReviewLanguage,
  ReviewLanguageEvidence,
  ReviewProduct,
  ReviewProjection,
  WorkbenchConnection,
  assertProductEvidence,
  assertReviewProjection,
  canSubmitDecision,
  filterReviewProducts,
  formatEvidenceForCopy,
  parseWorkbenchConnection,
  reviewLanguages,
  reviewMaterials,
} from "../review-model";

const statusLabels: Record<string, string> = {
  pending: "待审核",
  approved: "已批准",
  rejected: "已拒绝",
  passed: "通过",
  failed: "失败",
  blocked: "阻断",
  matched: "一致",
  mismatched: "不一致",
};

function initialConnection(): WorkbenchConnection {
  if (typeof window === "undefined") {
    return parseWorkbenchConnection("");
  }
  const fragmentAt = window.location.href.indexOf("#");
  return parseWorkbenchConnection(
    fragmentAt >= 0 ? window.location.href.slice(fragmentAt) : "",
  );
}

function statusTone(status: string): string {
  if (["approved", "passed", "matched"].includes(status)) return "success";
  if (["rejected", "failed", "blocked", "mismatched"].includes(status)) return "danger";
  return "pending";
}

function StatusPill({ status }: { status: string }) {
  return (
    <span className={`status-pill status-${statusTone(status)}`}>
      {statusLabels[status] ?? status}
    </span>
  );
}

function displayValue(value: unknown): string {
  return formatEvidenceForCopy(value);
}

function previewDocument(fragment: unknown): string {
  const html = typeof fragment === "string" ? fragment : `<pre>${displayValue(fragment)}</pre>`;
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'"><style>html{color:#1d2925;background:#fffdf8;font:14px/1.55 system-ui,sans-serif}body{margin:16px;overflow-wrap:anywhere}table{border-collapse:collapse;max-width:100%}th,td{border:1px solid #d5ddd8;padding:6px 8px;text-align:left}img{max-width:100%}pre{white-space:pre-wrap}</style></head><body>${html}</body></html>`;
}

async function responseDocument(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new Error(`本地审核服务返回了不可读取的响应（HTTP ${response.status}）。`);
  }
}

function responseError(value: unknown, fallback: string): string {
  if (value && typeof value === "object") {
    const error = (value as { error?: unknown }).error;
    if (error && typeof error === "object") {
      const message = (error as { message?: unknown }).message;
      if (typeof message === "string") return message;
    }
  }
  return fallback;
}

function Metric({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value.toLocaleString("zh-CN")}</strong>
      <small>{detail}</small>
    </article>
  );
}

function ProductQueue({
  products,
  selectedProductKey,
  onSelect,
}: {
  products: ReviewProduct[];
  selectedProductKey: string | null;
  onSelect: (productKey: string) => void;
}) {
  if (!products.length) {
    return <p className="empty-state">当前筛选条件下没有产品。</p>;
  }
  return (
    <ul className="product-list">
      {products.map((product) => (
        <li key={product.product_key}>
          <button
            type="button"
            className={`product-row ${selectedProductKey === product.product_key ? "selected" : ""}`}
            onClick={() => onSelect(product.product_key)}
          >
            <span className="product-row-main">
              <strong>{product.display_name}</strong>
              <small>{product.product_key}</small>
            </span>
            <span className="product-row-meta">
              <StatusPill status={product.status} />
              <small>{product.semantic_strategy}</small>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function MachineEvidence({ evidence }: { evidence: ReviewLanguageEvidence }) {
  const l3aStatus = String(evidence.l3a.status ?? "unknown");
  const l3bStatus = String(evidence.l3b.status ?? "unknown");
  return (
    <section className="machine-panel" aria-label={`${evidence.language} 机器检查`}>
      <div className="machine-card">
        <div><span>L3a</span><StatusPill status={l3aStatus} /></div>
        <strong>批处理幂等性</strong>
        <p>两次独立抽取的完整 Business Payload 是否一致。</p>
        <code>{evidence.paths.l3a_report}</code>
      </div>
      <div className="machine-card">
        <div><span>L3b</span><StatusPill status={l3bStatus} /></div>
        <strong>Source / Payload 内容一致性</strong>
        <p>{evidence.summary.matched}/{evidence.summary.comparisons} 项一致；独立于生产 Strategy。</p>
        <code>{evidence.paths.l3b_report}</code>
      </div>
    </section>
  );
}

function EvidenceSide({ label, value, kind }: { label: string; value: unknown; kind: "html" | "value" }) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (copyStatus === "idle") return undefined;
    const timeout = window.setTimeout(() => setCopyStatus("idle"), 2000);
    return () => window.clearTimeout(timeout);
  }, [copyStatus]);

  const copyContent = async () => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("浏览器没有提供剪贴板写入能力。");
      }
      await navigator.clipboard.writeText(formatEvidenceForCopy(value));
      setCopyStatus("copied");
    } catch {
      setCopyStatus("failed");
    }
  };

  const copyLabel = copyStatus === "copied"
    ? "已复制"
    : copyStatus === "failed"
      ? "复制失败"
      : "复制";

  return (
    <article className="evidence-side">
      <header>
        <span>{label}</span>
        <button
          type="button"
          className={`copy-evidence-button copy-${copyStatus}`}
          onClick={() => void copyContent()}
          aria-label={`复制${label}内容`}
          aria-live="polite"
          title="复制框内完整内容"
        >
          {copyLabel}
        </button>
      </header>
      {kind === "html" ? (
        <iframe
          className="fragment-preview"
          sandbox=""
          srcDoc={previewDocument(value)}
          title={`${label} HTML 片段预览`}
        />
      ) : (
        <pre className="value-preview">{displayValue(value)}</pre>
      )}
      <details className="raw-fragment">
        <summary>{kind === "html" ? "查看规范化 HTML" : "查看原始值"}</summary>
        <pre>{displayValue(value)}</pre>
      </details>
    </article>
  );
}

function ComparisonViewer({ comparison }: { comparison: ReviewComparison }) {
  return (
    <section className="comparison-viewer">
      <header className="comparison-heading">
        <div>
          <p className="eyebrow">{comparison.payload_path}</p>
          <h3>{comparison.label}</h3>
          <p>{comparison.source_boundary}</p>
        </div>
        <StatusPill status={comparison.status} />
      </header>
      <div className="comparison-grid">
        <EvidenceSide key={`${comparison.comparison_key}:source`} label="Frozen HTML 独立源片段" value={comparison.source} kind={comparison.kind} />
        <EvidenceSide key={`${comparison.comparison_key}:payload`} label="Payload 对应字段" value={comparison.payload} kind={comparison.kind} />
      </div>
      {comparison.difference ? (
        <details className="difference-panel">
          <summary>查看可读差异</summary>
          <pre>{displayValue(comparison.difference)}</pre>
        </details>
      ) : null}
    </section>
  );
}

interface DecisionDraft {
  reviewer: string;
  decision: ReviewDecision;
  notes: string;
  inspectedLanguages: ReviewLanguage[];
  inspectedMaterials: string[];
}

const emptyDecision: DecisionDraft = {
  reviewer: "",
  decision: "approved",
  notes: "",
  inspectedLanguages: [],
  inspectedMaterials: [],
};

function DecisionPanel({
  product,
  draft,
  onChange,
  onRequestSubmit,
  submitting,
}: {
  product: ProductEvidence["product"];
  draft: DecisionDraft;
  onChange: (draft: DecisionDraft) => void;
  onRequestSubmit: () => void;
  submitting: boolean;
}) {
  if (product.status !== "pending") {
    return (
      <section className="decision-panel decision-complete">
        <p className="eyebrow">不可覆盖的人工决定</p>
        <div className="decision-complete-line">
          <StatusPill status={product.status} />
          <strong>{product.reviewer}</strong>
        </div>
        <p>该产品已经有决定。需要重新审核时，请从同一 Batch 创建新的审核 ID。</p>
        {product.decision_path ? <code>{product.decision_path}</code> : null}
      </section>
    );
  }

  const toggleLanguage = (language: ReviewLanguage) => {
    const inspectedLanguages = draft.inspectedLanguages.includes(language)
      ? draft.inspectedLanguages.filter((item) => item !== language)
      : [...draft.inspectedLanguages, language];
    onChange({ ...draft, inspectedLanguages });
  };
  const toggleMaterial = (material: string) => {
    const inspectedMaterials = draft.inspectedMaterials.includes(material)
      ? draft.inspectedMaterials.filter((item) => item !== material)
      : [...draft.inspectedMaterials, material];
    onChange({ ...draft, inspectedMaterials });
  };
  const submitReady = canSubmitDecision(draft);

  return (
    <section className="decision-panel">
      <div>
        <p className="eyebrow">产品级人工决定</p>
        <h3>提交前确认实际检查范围</h3>
        <p>决定同时覆盖这个产品的中文和英文处理项。批准必须勾选全部语言与材料。</p>
      </div>
      <label className="field-control">
        <span>审核人</span>
        <input
          value={draft.reviewer}
          onChange={(event) => onChange({ ...draft, reviewer: event.target.value })}
          autoComplete="name"
          placeholder="请输入真实审核人姓名"
        />
      </label>
      <fieldset className="choice-fieldset">
        <legend>决定</legend>
        <label><input type="radio" name="decision" checked={draft.decision === "approved"} onChange={() => onChange({ ...draft, decision: "approved" })} />批准</label>
        <label><input type="radio" name="decision" checked={draft.decision === "rejected"} onChange={() => onChange({ ...draft, decision: "rejected" })} />拒绝</label>
      </fieldset>
      <fieldset className="choice-fieldset">
        <legend>已检查语言</legend>
        {reviewLanguages.map((language) => (
          <label key={language}>
            <input type="checkbox" checked={draft.inspectedLanguages.includes(language)} onChange={() => toggleLanguage(language)} />
            {language}
          </label>
        ))}
      </fieldset>
      <fieldset className="choice-fieldset material-choices">
        <legend>已检查材料</legend>
        {reviewMaterials.map(([material, label]) => (
          <label key={material}>
            <input type="checkbox" checked={draft.inspectedMaterials.includes(material)} onChange={() => toggleMaterial(material)} />
            {label}
          </label>
        ))}
      </fieldset>
      <label className="field-control">
        <span>审核说明</span>
        <textarea
          value={draft.notes}
          onChange={(event) => onChange({ ...draft, notes: event.target.value })}
          rows={4}
          placeholder="记录批准依据，或清楚说明拒绝原因。"
        />
      </label>
      <button type="button" className="decision-button" disabled={!submitReady || submitting} onClick={onRequestSubmit}>
        {submitting ? "正在提交…" : `准备${draft.decision === "approved" ? "批准" : "拒绝"}`}
      </button>
    </section>
  );
}

export default function ReviewWorkbench() {
  const [connection] = useState<WorkbenchConnection>(initialConnection);
  const [projection, setProjection] = useState<ReviewProjection | null>(null);
  const [selectedProductKey, setSelectedProductKey] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<ProductEvidence | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<ReviewLanguage>("zh-cn");
  const [selectedComparisonKey, setSelectedComparisonKey] = useState<string | null>(null);
  const [filters, setFilters] = useState<ReviewFilters>({ query: "", status: "pending", strategy: "all" });
  const [draft, setDraft] = useState<DecisionDraft>(emptyDecision);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const bridgeFetch = useCallback(async (path: string, init?: RequestInit): Promise<unknown> => {
    if (!connection.token) throw new Error("缺少本地审核服务令牌，请使用 review-serve 打印的完整页面地址进入。 ");
    const response = await fetch(`${connection.bridgeUrl}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${connection.token}`,
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
    const value = await responseDocument(response);
    if (!response.ok) throw new Error(responseError(value, `请求失败（HTTP ${response.status}）。`));
    return value;
  }, [connection]);

  const loadProjection = useCallback(async () => {
    const value = await bridgeFetch("/v1/review");
    assertReviewProjection(value);
    setProjection(value);
    setSelectedProductKey((current) => {
      if (current && value.products.some((product) => product.product_key === current)) return current;
      return value.products.find((product) => product.status === "pending")?.product_key ?? value.products[0]?.product_key ?? null;
    });
  }, [bridgeFetch]);

  const loadEvidence = useCallback(async (productKey: string) => {
    setLoadingEvidence(true);
    setError(null);
    try {
      const value = await bridgeFetch(`/v1/products/${encodeURIComponent(productKey)}/evidence`);
      assertProductEvidence(value);
      setEvidence(value);
      setSelectedLanguage("zh-cn");
      const chinese = value.languages.find((language) => language.language === "zh-cn") ?? value.languages[0];
      setSelectedComparisonKey(chinese.comparisons[0]?.comparison_key ?? null);
      setDraft((current) => ({ ...emptyDecision, reviewer: current.reviewer }));
    } catch (reason) {
      setEvidence(null);
      setError(reason instanceof Error ? reason.message : "无法读取产品证据。");
    } finally {
      setLoadingEvidence(false);
    }
  }, [bridgeFetch]);

  useEffect(() => {
    if (window.location.href.includes("#")) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    }
  }, []);

  useEffect(() => {
    if (!connection.token) {
      setError("缺少本地审核服务令牌，请从 review-serve 打印的完整页面地址进入。");
      return;
    }
    void loadProjection().catch((reason) => setError(reason instanceof Error ? reason.message : "无法读取审核清单。"));
  }, [connection.token, loadProjection]);

  useEffect(() => {
    if (selectedProductKey) void loadEvidence(selectedProductKey);
  }, [selectedProductKey, loadEvidence]);

  const filteredProducts = useMemo(
    () => filterReviewProducts(projection?.products ?? [], filters),
    [projection, filters],
  );
  const strategies = useMemo(
    () => [...new Set((projection?.products ?? []).map((product) => product.semantic_strategy))].sort(),
    [projection],
  );
  const languageEvidence = evidence?.languages.find((language) => language.language === selectedLanguage) ?? null;
  const selectedComparison = languageEvidence?.comparisons.find((comparison) => comparison.comparison_key === selectedComparisonKey) ?? languageEvidence?.comparisons[0] ?? null;

  const chooseLanguage = (language: ReviewLanguage) => {
    setSelectedLanguage(language);
    const nextLanguage = evidence?.languages.find((candidate) => candidate.language === language);
    setSelectedComparisonKey(nextLanguage?.comparisons[0]?.comparison_key ?? null);
  };

  const submitDecision = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!evidence || !canSubmitDecision(draft)) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await bridgeFetch(`/v1/products/${encodeURIComponent(evidence.product.product_key)}/decision`, {
        method: "POST",
        body: JSON.stringify({
          reviewer: draft.reviewer,
          decision: draft.decision,
          notes: draft.notes,
          inspected_languages: reviewLanguages.filter((language) => draft.inspectedLanguages.includes(language)),
          inspected_materials: reviewMaterials.map(([material]) => material).filter((material) => draft.inspectedMaterials.includes(material)),
        }),
      });
      setConfirming(false);
      setMessage(`${evidence.product.display_name} 的${draft.decision === "approved" ? "批准" : "拒绝"}决定已写入，不能覆盖。`);
      await loadProjection();
      await loadEvidence(evidence.product.product_key);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法提交人工决定。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="workbench-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">ACN Archaeologist Rewrite</p>
          <h1>双语人工审核台</h1>
        </div>
        <div className={`connection-state ${projection ? "connected" : "disconnected"}`}>
          <span aria-hidden="true" />
          {projection ? `已连接 · ${projection.review_id}` : "尚未连接"}
        </div>
      </header>

      {error ? <div className="notice notice-error" role="alert">{error}</div> : null}
      {message ? <div className="notice notice-success" role="status">{message}</div> : null}

      {projection ? (
        <>
          <section className="intro-panel">
            <div>
              <p className="eyebrow">
                {projection.incremental_run_name
                  ? `原增量 Batch · ${projection.incremental_run_name} · 重新处理记录 · ${projection.run_name}`
                  : `已封存 Batch · ${projection.run_name}`}
              </p>
              <h2>一个产品，一次完整双语决定</h2>
              <p>{projection.instructions[1]}</p>
            </div>
            <code>{projection.review_directory}</code>
          </section>
          <section className="metrics-grid" aria-label="审核统计">
            <Metric label="待审核" value={projection.summary.pending_products} detail={`${projection.summary.queued_items} 个双语处理项`} />
            <Metric label="已批准" value={projection.summary.approved_products} detail="可进入完整 Release" />
            <Metric label="已拒绝" value={projection.summary.rejected_products} detail="不会进入 Release" />
            <Metric label="未入队" value={projection.summary.not_queued_items} detail="机器检查失败或阻断" />
          </section>

          <div className="workbench-grid">
            <aside className="queue-panel">
              <header><p className="eyebrow">产品清单</p><h2>{filteredProducts.length} / {projection.products.length}</h2></header>
              <div className="filters">
                <label><span>查找产品</span><input value={filters.query} onChange={(event) => setFilters({ ...filters, query: event.target.value })} placeholder="名称或 Product Key" /></label>
                <div className="filter-row">
                  <label><span>状态</span><select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value as ReviewFilters["status"] })}><option value="all">全部</option><option value="pending">待审核</option><option value="approved">已批准</option><option value="rejected">已拒绝</option></select></label>
                  <label><span>Strategy</span><select value={filters.strategy} onChange={(event) => setFilters({ ...filters, strategy: event.target.value })}><option value="all">全部</option>{strategies.map((strategy) => <option key={strategy} value={strategy}>{strategy}</option>)}</select></label>
                </div>
              </div>
              <ProductQueue products={filteredProducts} selectedProductKey={selectedProductKey} onSelect={setSelectedProductKey} />
              {projection.not_queued_items.length ? (
                <details className="not-queued"><summary>查看 {projection.not_queued_items.length} 个未入队处理项</summary>{projection.not_queued_items.map((item) => <div key={item.item_id}><strong>{item.item_id}</strong><span>{item.reason}</span></div>)}</details>
              ) : null}
            </aside>

            <section className="detail-panel">
              {loadingEvidence ? <div className="loading-state">正在重新读取 Frozen HTML 与 Payload…</div> : null}
              {!loadingEvidence && evidence ? (
                <>
                  <header className="product-heading">
                    <div><p className="eyebrow">{evidence.product.product_key}</p><h2>{evidence.product.display_name}</h2><p>{evidence.product.page_model} · {evidence.product.semantic_strategy}</p></div>
                    <StatusPill status={evidence.product.status} />
                  </header>
                  <p className="method-note">{evidence.evidence_method}</p>
                  <div className="language-tabs" role="tablist" aria-label="审核语言">
                    {evidence.languages.map((language) => (
                      <button type="button" role="tab" aria-selected={selectedLanguage === language.language} className={selectedLanguage === language.language ? "active" : ""} key={language.language} onClick={() => chooseLanguage(language.language)}>
                        <span>{language.language}</span><small>{language.summary.matched}/{language.summary.comparisons} 一致</small>
                      </button>
                    ))}
                  </div>
                  {languageEvidence ? (
                    <>
                      <MachineEvidence evidence={languageEvidence} />
                      <details className="artifact-paths"><summary>查看本语言四类审核材料路径</summary><dl><dt>Frozen HTML</dt><dd><code>{languageEvidence.paths.frozen_html}</code></dd><dt>Payload</dt><dd><code>{languageEvidence.paths.payload}</code></dd><dt>L3a</dt><dd><code>{languageEvidence.paths.l3a_report}</code></dd><dt>L3b</dt><dd><code>{languageEvidence.paths.l3b_report}</code></dd></dl></details>
                      <section className="comparison-section">
                        <header><div><p className="eyebrow">完整字段清单</p><h3>选择一个 Source / Payload 对应项</h3></div><StatusPill status={languageEvidence.summary.mismatched ? "mismatched" : "matched"} /></header>
                        <label className="comparison-selector"><span>比较项</span><select value={selectedComparison?.comparison_key ?? ""} onChange={(event) => setSelectedComparisonKey(event.target.value)}>{languageEvidence.comparisons.map((comparison) => <option key={comparison.comparison_key} value={comparison.comparison_key}>{comparison.status === "matched" ? "✓" : "!"} {comparison.label} · {comparison.payload_path}</option>)}</select></label>
                        {selectedComparison ? <ComparisonViewer comparison={selectedComparison} /> : <p className="empty-state">本语言没有可展示的业务字段。</p>}
                      </section>
                    </>
                  ) : null}
                  <DecisionPanel product={evidence.product} draft={draft} onChange={setDraft} onRequestSubmit={() => setConfirming(true)} submitting={submitting} />
                </>
              ) : null}
            </section>
          </div>
        </>
      ) : (
        <section className="connection-help">
          <p className="eyebrow">Local only</p>
          <h2>请从本地审核服务生成的地址进入</h2>
          <p>先启动 Dashboard，再运行 <code>python cli.py review-serve --review-id &lt;审核 ID&gt;</code>。终端会打印包含临时令牌的完整审核页面地址。</p>
        </section>
      )}

      {confirming && evidence ? (
        <div className="modal-backdrop" role="presentation">
          <section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <p className="eyebrow">最后确认 · 不可覆盖</p>
            <h2 id="confirm-title">{draft.decision === "approved" ? "批准" : "拒绝"} {evidence.product.display_name}？</h2>
            <p>此决定同时绑定该产品当前审核清单中的中英文材料。提交后不能修改或删除。</p>
            <dl><dt>审核人</dt><dd>{draft.reviewer}</dd><dt>语言</dt><dd>{draft.inspectedLanguages.join("、")}</dd><dt>材料</dt><dd>{draft.inspectedMaterials.join("、")}</dd><dt>说明</dt><dd>{draft.notes}</dd></dl>
            <div className="modal-actions"><button type="button" className="secondary-button" disabled={submitting} onClick={() => setConfirming(false)}>返回检查</button><button type="button" className={`decision-button ${draft.decision === "rejected" ? "reject" : ""}`} disabled={submitting} onClick={() => void submitDecision()}>{submitting ? "正在写入…" : "确认并写入决定"}</button></div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
