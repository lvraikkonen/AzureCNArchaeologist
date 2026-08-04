"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  ItemEvidence,
  ReviewFilters,
  ReviewQueueItem,
  WorkbenchProjection,
  assertItemEvidence,
  assertWorkbenchProjection,
  bindingLabel,
  decisionLabel,
  defaultReviewFilters,
  filterReviewItems,
  shortSha,
} from "../review-model";

const rejectionReasons = [
  ["upstream_source", "上游 Source"],
  ["product_config", "产品配置"],
  ["extractor_defect", "提取器缺陷"],
  ["validator_defect", "验证器缺陷"],
  ["needs_clarification", "需要澄清"],
] as const;

function initialConnection(): { bridgeUrl: string; token: string | null; hadFragment: boolean } {
  if (typeof window === "undefined") {
    return {
      bridgeUrl: "http://127.0.0.1:8765",
      token: null,
      hadFragment: false,
    };
  }
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  return {
    bridgeUrl: (fragment.get("bridge") ?? "http://127.0.0.1:8765").replace(/\/$/, ""),
    token: fragment.get("token"),
    hadFragment: window.location.hash.length > 1,
  };
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function statusTone(value: string): string {
  if (value === "approved" || value === "eligible" || value === "bound") return "emerald";
  if (value === "rejected" || value === "stale" || value === "blocked") return "coral";
  if (value === "pending" || value === "not_applicable") return "amber";
  return "slate";
}

function Pill({ label, tone }: { label: string; tone: string }) {
  return <span className={`review-pill tone-${tone}`}>{label}</span>;
}

function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <article className="review-metric">
      <span>{label}</span>
      <strong>{value.toLocaleString("zh-CN")}</strong>
      <small>{detail}</small>
    </article>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <label className="review-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([optionValue, text]) => (
          <option key={optionValue} value={optionValue}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

function EvidenceBlock({
  title,
  source,
  payload,
}: {
  title: string;
  source: unknown;
  payload: unknown;
}) {
  return (
    <section className="review-evidence-block">
      <h4>{title}</h4>
      <div className="review-compare-grid">
        <div>
          <span>Source</span>
          <pre>{formatJson(source)}</pre>
        </div>
        <div>
          <span>Payload</span>
          <pre>{formatJson(payload)}</pre>
        </div>
      </div>
    </section>
  );
}

function QueueTable({
  items,
  selectedItemId,
  onSelect,
}: {
  items: ReviewQueueItem[];
  selectedItemId: string | null;
  onSelect: (item: ReviewQueueItem) => void;
}) {
  return (
    <div className="review-table-wrap">
      <table className="review-table">
        <thead>
          <tr>
            <th>Item</th>
            <th>语言</th>
            <th>状态</th>
            <th>绑定</th>
            <th>覆盖</th>
            <th>Release</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.item_id}
              className={selectedItemId === item.item_id ? "selected" : undefined}
            >
              <td>
                <button type="button" onClick={() => onSelect(item)}>
                  <strong>{item.resource_key}</strong>
                  <span>{item.product_key}</span>
                </button>
              </td>
              <td>{item.language}</td>
              <td>
                <Pill label={decisionLabel(item.status.review)} tone={statusTone(item.status.review)} />
              </td>
              <td>
                <Pill label={bindingLabel(item.status.evidence_binding)} tone={statusTone(item.status.evidence_binding)} />
              </td>
              <td>
                {item.coverage.mode === "full"
                  ? "full"
                  : `${item.coverage.selected_count}/${item.coverage.universe_count}`}
              </td>
              <td>{item.release_ready ? "ready" : "blocked"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ReviewWorkbench() {
  const [connection, setConnection] = useState({
    bridgeUrl: "http://127.0.0.1:8765",
    token: null as string | null,
    hadFragment: false,
  });
  const token = connection.token;
  const [batches, setBatches] = useState<string[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<string | null>(null);
  const [projection, setProjection] = useState<WorkbenchProjection | null>(null);
  const [selectedItem, setSelectedItem] = useState<ReviewQueueItem | null>(null);
  const [evidence, setEvidence] = useState<ItemEvidence | null>(null);
  const [filters, setFilters] = useState<ReviewFilters>(defaultReviewFilters);
  const [reviewer, setReviewer] = useState("");
  const [notes, setNotes] = useState("");
  const [verdict, setVerdict] = useState<"approved" | "rejected">("approved");
  const [reason, setReason] = useState("needs_clarification");
  const [pageGlobal, setPageGlobal] = useState(false);
  const [selectedStates, setSelectedStates] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const authFetch = useCallback(
    async (path: string, init: RequestInit = {}) => {
      if (!token) throw new Error("Workbench token is missing");
      const response = await fetch(`${connection.bridgeUrl}${path}`, {
        ...init,
        cache: "no-store",
        headers: {
          Authorization: `Bearer ${token}`,
          ...(init.body ? { "Content-Type": "application/json" } : {}),
          ...init.headers,
        },
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        const problem = payload as { error?: { code?: string; message?: string } };
        throw new Error(problem.error?.message ?? `Bridge request failed: ${response.status}`);
      }
      return payload;
    },
    [connection.bridgeUrl, token],
  );

  const loadProjection = useCallback(
    async (batchId: string) => {
      const payload = await authFetch(`/v1/batches/${encodeURIComponent(batchId)}/projection`);
      assertWorkbenchProjection(payload);
      setProjection(payload);
      setSelectedBatch(batchId);
      return payload;
    },
    [authFetch],
  );

  const loadEvidence = useCallback(
    async (batchId: string, item: ReviewQueueItem) => {
      setEvidence(null);
      setSelectedStates([]);
      setPageGlobal(false);
      const payload = await authFetch(
        `/v1/batches/${encodeURIComponent(batchId)}/items/${item.language}/${encodeURIComponent(item.resource_key)}/evidence`,
      );
      assertItemEvidence(payload);
      setEvidence(payload);
    },
    [authFetch],
  );

  useEffect(() => {
    const nextConnection = initialConnection();
    queueMicrotask(() => setConnection(nextConnection));
    if (nextConnection.hadFragment) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    let active = true;
    const loadInitial = async () => {
      setBusy(true);
      setError(null);
      try {
        const session = await authFetch("/v1/session");
        const nextBatches = Array.isArray((session as { batches?: unknown }).batches)
          ? ((session as { batches: string[] }).batches)
          : [];
        if (!active) return;
        setBatches(nextBatches);
        if (nextBatches[0]) await loadProjection(nextBatches[0]);
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : String(caught));
      } finally {
        if (active) setBusy(false);
      }
    };
    void loadInitial();
    return () => {
      active = false;
    };
  }, [authFetch, loadProjection, token]);

  const visibleItems = useMemo(
    () => filterReviewItems(projection?.items ?? [], filters),
    [filters, projection],
  );

  const selectedManualState = useMemo(() => {
    if (!evidence || selectedStates.length === 0) return null;
    return evidence.manual_preview.states.find((state) => state.state_id === selectedStates[0]) ?? null;
  }, [evidence, selectedStates]);

  const selectItem = useCallback(
    (item: ReviewQueueItem) => {
      if (!selectedBatch) return;
      setSelectedItem(item);
      setMessage(null);
      loadEvidence(selectedBatch, item).catch((caught: Error) => setError(caught.message));
    },
    [loadEvidence, selectedBatch],
  );

  const updateFilter = <Key extends keyof ReviewFilters>(
    key: Key,
    value: ReviewFilters[Key],
  ) => setFilters((current) => ({ ...current, [key]: value }));

  const submitDecision = async () => {
    if (!selectedBatch || !selectedItem || !projection || !evidence) return;
    const inspected_states =
      evidence.inspection.mode === "full"
        ? [{ scope: "full_content" }]
        : [
            ...(pageGlobal ? [{ scope: "page_global" }] : []),
            ...selectedStates.map((state_id) => ({ scope: "interactive_state", state_id })),
          ];
    setBusy(true);
    setError(null);
    try {
      const result = (await authFetch(
        `/v1/batches/${encodeURIComponent(selectedBatch)}/items/${selectedItem.language}/${encodeURIComponent(selectedItem.resource_key)}/decision`,
        {
          method: "POST",
          body: JSON.stringify({
            expected_revision: projection.batch.manifest_revision,
            reviewer,
            verdict,
            reason: verdict === "approved" ? null : reason,
            notes,
            inspected_states,
          }),
        },
      )) as { status?: string; review?: string };
      const refreshed = await loadProjection(selectedBatch);
      const nextItem = refreshed.items.find((item) => item.item_id === selectedItem.item_id) ?? null;
      setSelectedItem(nextItem);
      if (nextItem) await loadEvidence(selectedBatch, nextItem);
      setConfirming(false);
      setMessage(
        result.status === "committed_but_refresh_required"
          ? "决定已写入，但投影需要手动刷新。"
          : "决定已写入并刷新。"
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  const canSendDecision = Boolean(
    selectedItem &&
      evidence &&
      reviewer.trim() &&
      (evidence.inspection.mode === "full" || selectedStates.length > 0) &&
      (verdict === "approved" || reason) &&
      !(verdict === "approved" && selectedItem.approval_blocked),
  );
  const selectedSourceWarnings = selectedItem?.source_quality_findings.filter(
    (finding) => finding.classification === "advisory",
  ) ?? [];

  return (
    <main className="review-workbench">
      <header className="review-topbar">
        <Link className="brand" href="/" aria-label="返回 Capability Ledger">
          <span className="brand-mark" aria-hidden="true">
            AZ
          </span>
          <span>
            <strong>Azure CN Archaeologist</strong>
            <small>Review Workbench</small>
          </span>
        </Link>
        <div className="review-connection">
          <Pill label={token ? "local bridge" : "read only"} tone={token ? "emerald" : "amber"} />
          <span className="mono">{connection.bridgeUrl}</span>
        </div>
      </header>

      <section className="review-shell review-hero">
        <div>
          <p className="eyebrow">Step 5 · Slice C</p>
          <h1>受控 Review 工作台</h1>
          <p>
            明确选择 Batch，逐项查看 Source/Payload/Validation/Sampled Evidence，
            并通过受控服务写入 append-only Review Decision。
          </p>
        </div>
        <div className="review-batch-picker">
          <SelectField
            label="Batch"
            value={selectedBatch ?? ""}
            options={batches.map((batch) => [batch, batch])}
            onChange={(value) => {
              setSelectedItem(null);
              setEvidence(null);
              loadProjection(value).catch((caught: Error) => setError(caught.message));
            }}
          />
          <span>revision {projection?.batch.manifest_revision ?? "—"}</span>
        </div>
      </section>

      {!token ? (
        <section className="review-shell review-empty">
          <h2>未连接本地 Workbench bridge</h2>
          <p>
            先启动 `pipeline-review-serve`，再使用命令输出的 `/review#bridge=...&token=...`
            地址打开本页。无 token 时页面不会尝试读取或写入任何 Batch 状态。
          </p>
        </section>
      ) : null}

      {error ? <div className="review-shell review-alert">{error}</div> : null}
      {message ? <div className="review-shell review-alert success">{message}</div> : null}

      {projection ? (
        <>
          <section className="review-shell review-metrics" aria-label="Review overview">
            <Metric label="语言项" value={projection.summary.items.total} detail={`${projection.summary.items.pending} pending`} />
            <Metric label="产品" value={projection.summary.products.total} detail={`${projection.summary.products.pending_attention} 需处理`} />
            <Metric label="Release Ready" value={projection.summary.items.release_ready_count} detail={`${projection.summary.products.release_ready_count} 个产品`} />
            <Metric label="Source Warning" value={projection.summary.items.source_warning_count} detail={`${projection.summary.products.source_warning_count} 个产品`} />
            <Metric label="Approval Blocked" value={projection.summary.items.approval_blocked_count} detail={`${projection.summary.products.approval_blocked_count} 个产品`} />
            <Metric label="Machine Failed" value={projection.summary.items.machine_failed_count} detail={`${projection.summary.products.machine_failed_count} 个产品`} />
          </section>

          <section className="review-shell review-layout">
            <aside className="review-sidebar">
              <div className="review-filter-grid">
                <label className="review-field">
                  <span>搜索</span>
                  <input
                    value={filters.query}
                    onChange={(event) => updateFilter("query", event.target.value)}
                    placeholder="resource 或 product"
                  />
                </label>
                <SelectField
                  label="语言"
                  value={filters.language}
                  options={[
                    ["all", "全部"],
                    ["zh-cn", "zh-cn"],
                    ["en-us", "en-us"],
                  ]}
                  onChange={(value) => updateFilter("language", value as ReviewFilters["language"])}
                />
                <SelectField
                  label="Review"
                  value={filters.review}
                  options={[
                    ["all", "全部"],
                    ["pending", "待审"],
                    ["approved", "已批准"],
                    ["rejected", "已拒绝"],
                  ]}
                  onChange={(value) => updateFilter("review", value as ReviewFilters["review"])}
                />
                <SelectField
                  label="Binding"
                  value={filters.binding}
                  options={[
                    ["all", "全部"],
                    ["bound", "bound"],
                    ["stale", "stale"],
                    ["not_applicable", "not_applicable"],
                  ]}
                  onChange={(value) => updateFilter("binding", value as ReviewFilters["binding"])}
                />
                <SelectField
                  label="Coverage"
                  value={filters.coverage}
                  options={[
                    ["all", "全部"],
                    ["full", "full"],
                    ["stratified_sample", "sample"],
                  ]}
                  onChange={(value) => updateFilter("coverage", value as ReviewFilters["coverage"])}
                />
                <SelectField
                  label="Source"
                  value={filters.source}
                  options={[
                    ["all", "全部"],
                    ["warning", "warning"],
                    ["approval_blocked", "approval blocked"],
                    ["clear", "clear"],
                  ]}
                  onChange={(value) => updateFilter("source", value as ReviewFilters["source"])}
                />
                <SelectField
                  label="Release"
                  value={filters.release}
                  options={[
                    ["all", "全部"],
                    ["ready", "ready"],
                    ["blocked", "blocked"],
                  ]}
                  onChange={(value) => updateFilter("release", value as ReviewFilters["release"])}
                />
              </div>
              <QueueTable items={visibleItems} selectedItemId={selectedItem?.item_id ?? null} onSelect={selectItem} />
            </aside>

            <section className="review-detail">
              {selectedItem ? (
                <>
                  <header className="review-detail-head">
                    <div>
                      <p className="eyebrow">{selectedItem.item_id}</p>
                      <h2>{selectedItem.resource_key}</h2>
                    </div>
                    <div className="review-status-row">
                      <Pill label={decisionLabel(selectedItem.status.review)} tone={statusTone(selectedItem.status.review)} />
                      <Pill label={bindingLabel(selectedItem.status.evidence_binding)} tone={statusTone(selectedItem.status.evidence_binding)} />
                      {selectedItem.source_warning ? <Pill label="Source Warning" tone="amber" /> : null}
                      {selectedItem.approval_blocked ? <Pill label="Approval Blocked" tone="coral" /> : null}
                      <Pill label={selectedItem.release_ready ? "release ready" : "release blocked"} tone={selectedItem.release_ready ? "emerald" : "slate"} />
                    </div>
                  </header>

                  {selectedSourceWarnings.length ? (
                    <section className="review-warning-panel">
                      <h3>Source Warning</h3>
                      {selectedSourceWarnings.map((finding) => (
                        <article key={`${finding.code}:${finding.path ?? "$"}`}>
                          <strong>{finding.code}</strong>
                          <span>{finding.message}</span>
                          <code>{finding.path ?? "$"}</code>
                        </article>
                      ))}
                    </section>
                  ) : null}

                  {selectedItem.approval_blockers.length ? (
                    <section className="review-warning-panel blocked">
                      <h3>Approval Blocked</h3>
                      {selectedItem.approval_blockers.map((blocker) => (
                        <article key={`${blocker.code}:${blocker.path ?? "$"}`}>
                          <strong>{blocker.code}</strong>
                          <span>{blocker.message}</span>
                          <code>{blocker.path ?? "$"}</code>
                        </article>
                      ))}
                    </section>
                  ) : null}

                  {evidence?.manual_preview.status === "available" && evidence.manual_preview.page_global ? (
                    <EvidenceBlock
                      title="Page-global comparison"
                      source={evidence.manual_preview.page_global.source}
                      payload={evidence.manual_preview.page_global.payload}
                    />
                  ) : null}

                  {evidence?.manual_preview.full_content ? (
                    <EvidenceBlock
                      title="Full-content comparison"
                      source={evidence.manual_preview.full_content.source}
                      payload={evidence.manual_preview.full_content.payload}
                    />
                  ) : null}

                  {selectedManualState ? (
                    <EvidenceBlock
                      title={`State ${shortSha(selectedManualState.state_id)}`}
                      source={selectedManualState.comparison.source}
                      payload={selectedManualState.comparison.payload}
                    />
                  ) : null}

                  {evidence?.manual_preview.status === "unavailable" ? (
                    <section className="review-empty inline">
                      <h3>Manual preview 暂不可用</h3>
                      <p>{evidence.manual_preview.error?.message}</p>
                    </section>
                  ) : null}

                  <section className="review-inspection">
                    <h3>检查范围</h3>
                    {evidence?.inspection.mode === "full" ? (
                      <label className="review-check">
                        <input type="checkbox" checked readOnly />
                        Full content
                      </label>
                    ) : (
                      <>
                        <label className="review-check">
                          <input
                            type="checkbox"
                            checked={pageGlobal}
                            onChange={(event) => setPageGlobal(event.target.checked)}
                          />
                          Page-global
                        </label>
                        <div className="review-state-list">
                          {evidence?.inspection.state_universe.map((state) => {
                            const checked = selectedStates.includes(state.state_id);
                            const machineSelected = evidence.coverage.selected_state_ids?.includes(state.state_id);
                            return (
                              <label className={machineSelected ? "review-check" : "review-check priority"} key={state.state_id}>
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={(event) => {
                                    setSelectedStates((current) =>
                                      event.target.checked
                                        ? [...current, state.state_id]
                                        : current.filter((value) => value !== state.state_id),
                                    );
                                  }}
                                />
                                <span className="mono">{shortSha(state.state_id)}</span>
                                <small>{state.criteria.map((pair) => pair.join("=")).join(" / ")}</small>
                              </label>
                            );
                          })}
                        </div>
                      </>
                    )}
                  </section>

                  <section className="review-decision-panel">
                    <h3>写入 Review Decision</h3>
                    <form
                      onSubmit={(event: FormEvent) => {
                        event.preventDefault();
                        setConfirming(true);
                      }}
                    >
                      <label className="review-field">
                        <span>Reviewer</span>
                        <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
                      </label>
                      <SelectField
                        label="Verdict"
                        value={verdict}
                        options={[
                          ["approved", "批准"],
                          ["rejected", "拒绝"],
                        ]}
                        onChange={(value) => setVerdict(value as "approved" | "rejected")}
                      />
                      {verdict === "rejected" ? (
                        <SelectField
                          label="Reason"
                          value={reason}
                          options={rejectionReasons}
                          onChange={setReason}
                        />
                      ) : null}
                      <label className="review-field wide">
                        <span>Notes</span>
                        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
                      </label>
                      <button className="primary-action" type="submit" disabled={!canSendDecision || busy}>
                        {busy ? "处理中" : "准备确认"}
                      </button>
                    </form>
                  </section>

                  {evidence?.decisions.history.length ? (
                    <section className="review-history">
                      <h3>Decision history</h3>
                      {evidence.decisions.history.map((decision) => (
                        <article key={decision.decision_id}>
                          <strong>{decision.verdict}</strong>
                          <span>{decision.reviewer} · {decision.decided_at}</span>
                          <p>{decision.reason ?? "approved"}</p>
                        </article>
                      ))}
                    </section>
                  ) : null}
                </>
              ) : (
                <section className="review-empty inline">
                  <h2>选择一个 Review item</h2>
                  <p>左侧列表只展示当前 Batch 中机器执行成功且 Validation passed 的可审语言项。</p>
                </section>
              )}
            </section>
          </section>
        </>
      ) : null}

      {confirming && selectedItem ? (
        <div className="review-modal-backdrop">
          <section className="review-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <h2 id="confirm-title">确认写入决定</h2>
            <dl>
              <dt>Item</dt>
              <dd className="mono">{selectedItem.item_id}</dd>
              <dt>Revision</dt>
              <dd>{projection?.batch.manifest_revision}</dd>
              <dt>Verdict</dt>
              <dd>{verdict}</dd>
              <dt>Scopes</dt>
              <dd>{evidence?.inspection.mode === "full" ? "full_content" : `${pageGlobal ? "page_global " : ""}${selectedStates.length} states`}</dd>
            </dl>
            {selectedSourceWarnings.length ? (
              <div className="review-modal-warning">
                <strong>Source Warning</strong>
                {selectedSourceWarnings.map((finding) => (
                  <p key={`${finding.code}:${finding.path ?? "$"}`}>{finding.code}: {finding.message}</p>
                ))}
              </div>
            ) : null}
            <div className="review-modal-actions">
              <button type="button" className="secondary-action" onClick={() => setConfirming(false)}>
                取消
              </button>
              <button type="button" className="primary-action" onClick={submitDecision} disabled={busy}>
                写入 append-only decision
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
