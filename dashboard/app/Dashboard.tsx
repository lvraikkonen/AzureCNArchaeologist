"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  countOpenFindings,
  defaultFilters,
  deriveSummary,
  distinctValues,
  emptyStateMessage,
  filterAndSortProducts,
  formatMachineDiagnostic,
  getAttentionProducts,
  getBindingFacet,
  getManualLanguageDisplay,
  getProductDetail,
  type BindingFacet,
  type DashboardProjection,
  type Finding,
  type LanguageCode,
  type MachineLanguageStatus,
  type ManualOutcome,
  type ManualVerdict,
  type ProductFilters,
  type ProductProjection,
} from "./dashboard-model";

const languageNames: Record<LanguageCode, string> = {
  "zh-cn": "中文（zh-cn）",
  "en-us": "英文（en-us）",
};

const machineOutcomeLabels: Record<string, string> = {
  bilingual_pass: "双语机器通过",
  single_language_pass: "单语言机器通过",
  bilingual_fail: "双语机器失败",
  known_unsupported: "已知不支持",
};

const manualOutcomeLabels: Record<ManualOutcome, string> = {
  passed: "明确通过",
  failed: "明确失败",
  findings: "有待处理发现",
  pending: "待检查",
  stale: "证据已漂移",
  not_applicable: "不适用",
};

const bindingLabels: Record<BindingFacet, string> = {
  bound: "已绑定",
  legacy_unbound: "历史未绑定",
  stale: "已漂移",
  unrecorded: "尚无记录",
  not_applicable: "不适用",
};

const strategyLabels: Record<string, string> = {
  simple_static: "简单静态",
  region_filter: "区域筛选",
  complex: "复杂内容",
  support_article: "支持文章",
  none: "未配置",
};

const categoryLabels: Record<string, string> = {
  "ai-ml": "AI 与机器学习",
  analysis: "分析",
  "azure-virtual-desktop": "Azure 虚拟桌面",
  compute: "计算",
  container: "容器",
  database: "数据库",
  "dev-ops": "DevOps",
  "dev-tools": "开发工具",
  "hybrid-multicloud": "混合与多云",
  identity: "身份",
  integration: "集成",
  iot: "物联网",
  management: "管理与治理",
  migration: "迁移",
  networking: "网络",
  security: "安全",
  storage: "存储",
  websites: "Web",
};

type Tone =
  | "azure"
  | "emerald"
  | "amber"
  | "coral"
  | "slate"
  | "violet";

interface Segment {
  label: string;
  value: number;
  tone: Tone;
}

function formatDate(value: string): string {
  if (!value) return "未提供";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "UTC",
  }).format(parsed);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function shortSha(value: string | null | undefined): string {
  if (!value) return "—";
  return `${value.slice(0, 10)}…${value.slice(-8)}`;
}

function machineStatusLabel(status: MachineLanguageStatus): string {
  if (status === "pass") return "机器通过";
  if (status === "fail") return "机器失败";
  return "不适用";
}

function toneForMachine(status: MachineLanguageStatus): Tone {
  if (status === "pass") return "emerald";
  if (status === "fail") return "coral";
  return "slate";
}

function toneForManual(status: ManualOutcome | ManualVerdict): Tone {
  if (status === "passed") return "emerald";
  if (status === "failed" || status === "stale") return "coral";
  if (status === "findings" || status === "pending") return "amber";
  return "slate";
}

function toneForBinding(status: BindingFacet): Tone {
  if (status === "bound") return "emerald";
  if (status === "stale") return "coral";
  if (status === "legacy_unbound") return "amber";
  return "slate";
}

function iconForTone(tone: Tone): string {
  if (tone === "emerald") return "✓";
  if (tone === "coral") return "×";
  if (tone === "amber") return "!";
  if (tone === "violet") return "◆";
  if (tone === "azure") return "↗";
  return "○";
}

function StatusPill({
  label,
  tone,
  compact = false,
}: {
  label: string;
  tone: Tone;
  compact?: boolean;
}) {
  return (
    <span className={`status-pill tone-${tone}${compact ? " compact" : ""}`}>
      <span className="status-icon" aria-hidden="true">
        {iconForTone(tone)}
      </span>
      {label}
    </span>
  );
}

function ProgressTrack({
  title,
  total,
  basis,
  segments,
}: {
  title: string;
  total: number;
  basis: string;
  segments: Segment[];
}) {
  const safeTotal = Math.max(total, 1);
  const describedSegments = segments
    .filter((segment) => segment.value > 0)
    .map((segment) => `${segment.label} ${segment.value}`)
    .join("，");

  return (
    <article className="progress-card">
      <div className="progress-heading">
        <div>
          <h3>{title}</h3>
          <p>{basis}</p>
        </div>
        <strong>{formatNumber(total)}</strong>
      </div>
      <div
        className="segmented-track"
        role="img"
        aria-label={`${title}：${describedSegments}`}
      >
        {segments.map((segment) =>
          segment.value > 0 ? (
            <span
              className={`segment tone-${segment.tone}`}
              key={segment.label}
              style={{ width: `${(segment.value / safeTotal) * 100}%` }}
            />
          ) : null,
        )}
      </div>
      <div className="segment-legend">
        {segments.map((segment) => (
          <span key={segment.label}>
            <i className={`legend-dot tone-${segment.tone}`} />
            <span>{segment.label}</span>
            <strong>{formatNumber(segment.value)}</strong>
          </span>
        ))}
      </div>
    </article>
  );
}

function AttentionCard({
  product,
  onOpen,
}: {
  product: ProductProjection;
  onOpen: (productKey: string) => void;
}) {
  const findingCount = countOpenFindings(product);
  const tone = toneForManual(product.manual_outcome);
  const summary =
    product.manual_outcome === "findings"
      ? `${findingCount || 1} 条人工发现待厘清`
      : product.manual_outcome === "stale"
        ? "绑定 SHA 与当前机器证据不一致"
        : "仍有机器通过语言等待人工检查";

  return (
    <button
      className={`attention-card tone-border-${tone}`}
      type="button"
      onClick={() => onOpen(product.product_key)}
      data-product-key={product.product_key}
      aria-label={`查看 ${product.display_name} 详情`}
    >
      <span className={`attention-symbol tone-${tone}`} aria-hidden="true">
        {iconForTone(tone)}
      </span>
      <span className="attention-copy">
        <span className="attention-kicker">
          {manualOutcomeLabels[product.manual_outcome]}
        </span>
        <strong>{product.display_name}</strong>
        <span>{summary}</span>
      </span>
      <span className="attention-arrow" aria-hidden="true">
        →
      </span>
    </button>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="filter-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

function findingText(finding: Finding): string {
  if (finding.summary) return finding.summary;
  if (finding.details) return finding.details;
  if (finding.code) return finding.code;
  return JSON.stringify(finding);
}

function EvidenceLine({
  label,
  value,
  mono = false,
  title,
}: {
  label: string;
  value: string | number | null;
  mono?: boolean;
  title?: string;
}) {
  return (
    <div className="evidence-line">
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined} title={title}>
        {value === null || value === "" ? "—" : value}
      </dd>
    </div>
  );
}

function LanguageEvidence({
  language,
  product,
}: {
  language: LanguageCode;
  product: ProductProjection;
}) {
  const evidence = product.languages[language];
  const machineTone = toneForMachine(evidence.machine.status);
  const manualDisplay = getManualLanguageDisplay(evidence.manual);
  const manualTone = toneForManual(manualDisplay.status);
  const issues = [
    ...(evidence.machine.error ? [evidence.machine.error] : []),
    ...evidence.machine.validation_errors,
  ];

  return (
    <section className="language-evidence" aria-labelledby={`${product.product_key}-${language}`}>
      <div className="language-heading">
        <div>
          <p className="eyebrow">语言证据</p>
          <h3 id={`${product.product_key}-${language}`}>
            {languageNames[language]}
          </h3>
        </div>
        <div className="language-statuses">
          <StatusPill
            label={machineStatusLabel(evidence.machine.status)}
            tone={machineTone}
          />
          <StatusPill
            label={`人工：${manualDisplay.label}`}
            tone={manualTone}
          />
        </div>
      </div>

      <div className="evidence-columns">
        <div className="evidence-block">
          <h4>机器证据</h4>
          <dl>
            <EvidenceLine
              label="Content Groups"
              value={evidence.machine.content_group_count}
            />
            <EvidenceLine
              label="执行"
              value={evidence.machine.execution}
            />
            <EvidenceLine
              label="验证"
              value={evidence.machine.validation}
            />
            <EvidenceLine
              label="Source SHA"
              value={evidence.machine.source_sha256}
              mono
            />
            <EvidenceLine
              label="Payload SHA"
              value={evidence.machine.payload_sha256}
              mono
            />
          </dl>

          {issues.length > 0 ? (
            <div className="issue-block tone-border-coral">
              <strong>错误</strong>
              <ul>
                {issues.map((issue, index) => (
                  <li key={`${issue.code ?? "error"}-${index}`}>
                    {formatMachineDiagnostic(issue)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {evidence.machine.validation_warnings.length > 0 ? (
            <div className="issue-block tone-border-amber">
              <strong>警告</strong>
              <ul>
                {evidence.machine.validation_warnings.map((warning, index) => (
                  <li key={`${warning.code ?? "warning"}-${index}`}>
                    {formatMachineDiagnostic(warning)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="evidence-block">
          <h4>人工内容检查</h4>
          <dl>
            <EvidenceLine
              label="证据绑定"
              value={bindingLabels[getBindingFacet(evidence.manual)]}
            />
            <EvidenceLine label="检查人" value={evidence.manual.reviewer} />
            <EvidenceLine
              label="检查日期"
              value={evidence.manual.reviewed_at}
            />
            <EvidenceLine
              label="绑定 Source SHA"
              value={evidence.manual.source_sha256}
              mono
            />
            <EvidenceLine
              label="绑定 Payload SHA"
              value={evidence.manual.payload_sha256}
              mono
            />
          </dl>

          {evidence.manual.notes.length > 0 ? (
            <div className="note-block">
              <strong>备注</strong>
              <ul>
                {evidence.manual.notes.map((note, index) => (
                  <li key={`${note}-${index}`}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {evidence.manual.findings.length > 0 ? (
            <div className="issue-block tone-border-amber">
              <strong>人工发现</strong>
              <ul>
                {evidence.manual.findings.map((finding, index) => (
                  <li key={`${finding.code ?? "finding"}-${index}`}>
                    {findingText(finding)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>

      <details className="path-details">
        <summary>查看本地证据路径</summary>
        <dl>
          <EvidenceLine
            label="Source"
            value={evidence.machine.source_path}
            mono
          />
          <EvidenceLine
            label="Payload"
            value={evidence.machine.payload_path}
            mono
          />
        </dl>
      </details>
    </section>
  );
}

function ProductDrawer({
  product,
  onClose,
}: {
  product: ProductProjection | null;
  onClose: () => void;
}) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!product) return;
    closeButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;

      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), summary, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    document.body.classList.add("drawer-open");
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.classList.remove("drawer-open");
    };
  }, [onClose, product]);

  if (!product) return null;

  return (
    <div
      className="drawer-backdrop"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onClose();
      }}
    >
      <aside
        className="product-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="product-drawer-title"
        ref={drawerRef}
      >
        <div className="drawer-topbar">
          <div className="drawer-label">
            <span className="mono">{product.product_key}</span>
            <StatusPill
              compact
              label={bindingLabels[getBindingFacet(product)]}
              tone={toneForBinding(getBindingFacet(product))}
            />
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            ref={closeButtonRef}
            aria-label="关闭产品详情"
          >
            ×
          </button>
        </div>

        <div className="drawer-content">
          <header className="drawer-header">
            <p className="eyebrow">产品证据详情</p>
            <h2 id="product-drawer-title">{product.display_name}</h2>
            <div className="drawer-status-row">
              <StatusPill
                label={machineOutcomeLabels[product.machine_outcome]}
                tone={
                  product.machine_outcome === "bilingual_pass"
                    ? "emerald"
                    : product.machine_outcome === "single_language_pass"
                      ? "amber"
                      : product.machine_outcome === "bilingual_fail"
                        ? "coral"
                        : "slate"
                }
              />
              <StatusPill
                label={`人工：${manualOutcomeLabels[product.manual_outcome]}`}
                tone={toneForManual(product.manual_outcome)}
              />
            </div>
            <p className="drawer-description">
              {product.unsupported_reason ??
                "这里并列展示机器证据与人工内容检查；两类结论保持独立。"}
            </p>
            <div className="category-row">
              {product.catalog_categories.map((category) => (
                <span className="category-chip" key={category}>
                  {categoryLabels[category] ?? category}
                </span>
              ))}
              <span className="strategy-chip">
                {strategyLabels[product.semantic_strategy ?? "none"] ??
                  product.semantic_strategy}
              </span>
            </div>
          </header>

          {product.unscoped_findings.length > 0 ? (
            <section className="unscoped-findings">
              <div>
                <span className="attention-symbol tone-amber" aria-hidden="true">
                  !
                </span>
              </div>
              <div>
                <h3>未绑定到语言的历史发现</h3>
                <p>
                  这些记录保留原有价值，但未推测 zh-cn 或 en-us 的正式结论。
                </p>
                <ul>
                  {product.unscoped_findings.map((finding, index) => (
                    <li key={`${finding.code ?? "finding"}-${index}`}>
                      {findingText(finding)}
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          ) : null}

          <LanguageEvidence language="zh-cn" product={product} />
          <LanguageEvidence language="en-us" product={product} />

          {product.manual_notes.length > 0 ? (
            <section className="legacy-note-section">
              <h3>人工原始备注</h3>
              <ul>
                {product.manual_notes.map((note, index) => (
                  <li key={`${note}-${index}`}>{note}</li>
                ))}
              </ul>
            </section>
          ) : null}

          {product.raw_legacy ? (
            <details className="raw-record">
              <summary>查看迁移前原始记录</summary>
              <pre>{JSON.stringify(product.raw_legacy, null, 2)}</pre>
            </details>
          ) : null}

          <footer className="drawer-footer">
            <a
              href={product.url}
              target="_blank"
              rel="noreferrer"
              className="source-link"
            >
              打开 Azure 中国区源页面
              <span aria-hidden="true">↗</span>
            </a>
            <span>Slug · {product.slug}</span>
          </footer>
        </div>
      </aside>
    </div>
  );
}

export default function Dashboard({
  projection,
}: {
  projection: DashboardProjection;
}) {
  const derivedSummary = useMemo(
    () => deriveSummary(projection.products),
    [projection.products],
  );
  const [filters, setFilters] = useState<ProductFilters>(defaultFilters);
  const [selectedProductKey, setSelectedProductKey] = useState<string | null>(
    null,
  );
  const openerRef = useRef<HTMLElement | null>(null);

  const categories = useMemo(
    () =>
      distinctValues(projection.products, (product) =>
        product.catalog_categories,
      ),
    [projection.products],
  );
  const strategies = useMemo(
    () =>
      distinctValues(projection.products, (product) => [
        product.semantic_strategy ?? "none",
      ]),
    [projection.products],
  );
  const filteredProducts = useMemo(
    () => filterAndSortProducts(projection.products, filters),
    [filters, projection.products],
  );
  const attentionProducts = useMemo(
    () => getAttentionProducts(projection.products),
    [projection.products],
  );
  const selectedProduct = useMemo(
    () => getProductDetail(projection.products, selectedProductKey),
    [projection.products, selectedProductKey],
  );

  const updateFilter = useCallback(
    <Key extends keyof ProductFilters>(
      key: Key,
      value: ProductFilters[Key],
    ) => {
      setFilters((current) => ({ ...current, [key]: value }));
    },
    [],
  );

  const openProduct = useCallback((productKey: string) => {
    openerRef.current = document.activeElement as HTMLElement | null;
    setSelectedProductKey(productKey);
  }, []);

  const closeProduct = useCallback(() => {
    setSelectedProductKey(null);
    window.requestAnimationFrame(() => openerRef.current?.focus());
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(defaultFilters);
  }, []);

  const bindingUnreviewed = Math.max(
    derivedSummary.manual.reviewable_products -
      derivedSummary.binding.bound -
      derivedSummary.binding.legacy_unbound -
      derivedSummary.binding.stale,
    0,
  );
  const attentionCount =
    derivedSummary.manual.findings_products +
    derivedSummary.manual.pending_products +
    derivedSummary.binding.stale;
  const sourceKind =
    projection.source.machine_evidence.kind === "step3_probe"
      ? "Step 3 Capability Probe"
      : projection.source.machine_evidence.kind;

  return (
    <>
      <a className="skip-link" href="#product-inventory">
        跳到产品列表
      </a>
      <header className="site-header">
        <div className="shell site-header-inner">
          <a className="brand" href="#overview" aria-label="返回概览">
            <span className="brand-mark" aria-hidden="true">
              AZ
            </span>
            <span>
              <strong>Azure CN Archaeologist</strong>
              <small>Capability Ledger</small>
            </span>
          </a>
          <nav aria-label="页面导航">
            <a href="#evidence-tracks">证据轨道</a>
            <a href="#attention">需要关注</a>
            <a href="#product-inventory">产品列表</a>
          </nav>
          <div className="header-status">
            <span className="read-only-dot" />
            本地只读
          </div>
        </div>
      </header>

      <main id="overview">
        <section className="hero shell">
          <div className="hero-copy">
            <div className="hero-badges">
              <span className="version-badge">v0.4 · Step 3</span>
              <span className="evidence-badge">
                {projection.source.machine_evidence.formal_batch_created
                  ? "Batch Evidence"
                  : "Non-Batch Evidence"}
              </span>
            </div>
            <p className="eyebrow">Azure 中国区 · 能力证据投影</p>
            <h1>
              产品能力追踪，
              <span>每一条结论都有出处。</span>
            </h1>
            <p className="hero-intro">
              将固定范围、机器验证和人工内容检查并列呈现。页面只读，所有状态均由版本化
              JSON 投影生成。
            </p>
            <div className="hero-actions">
              <a className="primary-action" href="#product-inventory">
                浏览 {formatNumber(derivedSummary.scope.total)} 个产品
                <span aria-hidden="true">↓</span>
              </a>
              <a className="secondary-action" href="#attention">
                查看 {formatNumber(attentionCount)} 个关注项
              </a>
            </div>
          </div>

          <aside className="evidence-card" aria-label="当前证据快照">
            <div className="evidence-card-top">
              <span className="evidence-orbit" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              <StatusPill
                label={
                  projection.source.machine_evidence.formal_batch_created
                    ? "正式 Batch"
                    : "持久化非 Batch"
                }
                tone={
                  projection.source.machine_evidence.formal_batch_created
                    ? "emerald"
                    : "violet"
                }
              />
            </div>
            <p>当前机器证据</p>
            <h2>{sourceKind}</h2>
            <dl>
              <EvidenceLine
                label="报告"
                value={projection.source.machine_evidence.report_id}
                mono
              />
              <EvidenceLine
                label="Schema"
                value={projection.source.machine_evidence.schema_version}
                mono
              />
              <EvidenceLine
                label="数据日期"
                value={formatDate(projection.data_date)}
              />
              <EvidenceLine
                label="Evidence SHA"
                value={shortSha(projection.source.machine_evidence.sha256)}
                mono
                title={projection.source.machine_evidence.sha256}
              />
            </dl>
            <p className="evidence-note">
              证据源由配置显式选择，不按磁盘时间自动切换。
            </p>
          </aside>
        </section>

        <section className="kpi-section shell" aria-label="关键指标">
          <article className="kpi-card featured">
            <span className="kpi-index">01</span>
            <p>固定产品范围</p>
            <strong>{formatNumber(derivedSummary.scope.total)}</strong>
            <span>唯一 Azure 中国区入口</span>
          </article>
          <article className="kpi-card">
            <span className="kpi-index">02</span>
            <p>系统已支持</p>
            <strong>{formatNumber(derivedSummary.scope.supported)}</strong>
            <span>
              另有 {formatNumber(derivedSummary.scope.known_unsupported)}{" "}
              个已知不支持
            </span>
          </article>
          <article className="kpi-card">
            <span className="kpi-index">03</span>
            <p>机器通过语言项</p>
            <strong>
              {formatNumber(derivedSummary.machine.passed_language_items)}
            </strong>
            <span>zh-cn 与 en-us 分开计数</span>
          </article>
          <article className="kpi-card">
            <span className="kpi-index">04</span>
            <p>人工明确结论</p>
            <strong>
              {formatNumber(derivedSummary.manual.clear_conclusions)}
            </strong>
            <span>
              / {formatNumber(derivedSummary.manual.reviewable_products)}{" "}
              个可检查产品
            </span>
          </article>
          <article className="kpi-card attention-kpi">
            <span className="kpi-index">05</span>
            <p>当前需关注</p>
            <strong>{formatNumber(attentionCount)}</strong>
            <span>发现、待检查与证据漂移</span>
          </article>
        </section>

        <section className="section shell" id="evidence-tracks">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Four evidence tracks</p>
              <h2>四条轨道，互不覆盖</h2>
            </div>
            <p>
              capability、机器结果、人工内容检查和 SHA
              绑定分别统计，避免把不同性质的证据压成一个分数。
            </p>
          </div>
          <div className="progress-grid">
            <ProgressTrack
              title="Capability"
              total={derivedSummary.scope.total}
              basis="固定 105 项 scope"
              segments={[
                {
                  label: "已支持",
                  value: derivedSummary.scope.supported,
                  tone: "azure",
                },
                {
                  label: "已知不支持",
                  value: derivedSummary.scope.known_unsupported,
                  tone: "slate",
                },
              ]}
            />
            <ProgressTrack
              title="机器双语结果"
              total={derivedSummary.scope.supported}
              basis="仅系统已支持产品"
              segments={[
                {
                  label: "双语通过",
                  value: derivedSummary.machine.bilingual_pass,
                  tone: "emerald",
                },
                {
                  label: "单语言通过",
                  value: derivedSummary.machine.single_language_pass,
                  tone: "amber",
                },
                {
                  label: "双语失败",
                  value: derivedSummary.machine.bilingual_fail,
                  tone: "coral",
                },
              ]}
            />
            <ProgressTrack
              title="人工内容检查"
              total={derivedSummary.manual.reviewable_products}
              basis="至少一个机器通过语言"
              segments={[
                {
                  label: "明确结论",
                  value: derivedSummary.manual.clear_conclusions,
                  tone: "emerald",
                },
                {
                  label: "有发现",
                  value: derivedSummary.manual.findings_products,
                  tone: "amber",
                },
                {
                  label: "待检查",
                  value: derivedSummary.manual.pending_products,
                  tone: "slate",
                },
                {
                  label: "已漂移",
                  value: derivedSummary.binding.stale,
                  tone: "coral",
                },
              ]}
            />
            <ProgressTrack
              title="证据绑定"
              total={derivedSummary.manual.reviewable_products}
              basis="人工检查记录与当前机器证据"
              segments={[
                {
                  label: "已绑定",
                  value: derivedSummary.binding.bound,
                  tone: "emerald",
                },
                {
                  label: "历史未绑定",
                  value: derivedSummary.binding.legacy_unbound,
                  tone: "amber",
                },
                {
                  label: "已漂移",
                  value: derivedSummary.binding.stale,
                  tone: "coral",
                },
                {
                  label: "尚无记录",
                  value: bindingUnreviewed,
                  tone: "slate",
                },
              ]}
            />
          </div>
        </section>

        <section className="attention-section" id="attention">
          <div className="shell">
            <div className="section-heading attention-heading">
              <div>
                <p className="eyebrow">Attention queue</p>
                <h2>需要关注</h2>
              </div>
              <p>
                {formatNumber(derivedSummary.manual.findings_products)}{" "}
                个有发现 ·{" "}
                {formatNumber(derivedSummary.manual.pending_products)}{" "}
                个待检查 · {formatNumber(derivedSummary.binding.stale)}{" "}
                个已漂移
              </p>
            </div>

            {attentionProducts.length > 0 ? (
              <div className="attention-grid">
                {attentionProducts.map((product) => (
                  <AttentionCard
                    key={product.product_key}
                    product={product}
                    onOpen={openProduct}
                  />
                ))}
              </div>
            ) : (
              <div className="all-clear">
                <span aria-hidden="true">✓</span>
                <div>
                  <strong>当前没有需要关注的产品</strong>
                  <p>所有可检查项均已有明确且未漂移的记录。</p>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="section inventory-section shell" id="product-inventory">
          <div className="section-heading inventory-heading">
            <div>
              <p className="eyebrow">Product inventory</p>
              <h2>产品证据目录</h2>
            </div>
            <p>按名称、分类、策略和证据状态组合定位；选择产品查看双语详情。</p>
          </div>

          <div className="filter-panel">
            <label className="search-field">
              <span>搜索产品</span>
              <div>
                <span aria-hidden="true">⌕</span>
                <input
                  type="search"
                  value={filters.query}
                  onChange={(event) => updateFilter("query", event.target.value)}
                  placeholder="名称、Product Key、Slug…"
                />
                {filters.query ? (
                  <button
                    type="button"
                    onClick={() => updateFilter("query", "")}
                    aria-label="清空搜索"
                  >
                    ×
                  </button>
                ) : null}
              </div>
            </label>

            <div className="filter-grid">
              <FilterSelect
                label="分类"
                value={filters.category}
                onChange={(value) => updateFilter("category", value)}
              >
                <option value="all">全部分类</option>
                {categories.map((category) => (
                  <option value={category} key={category}>
                    {categoryLabels[category] ?? category}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="策略"
                value={filters.strategy}
                onChange={(value) => updateFilter("strategy", value)}
              >
                <option value="all">全部策略</option>
                {strategies.map((strategy) => (
                  <option value={strategy} key={strategy}>
                    {strategyLabels[strategy] ?? strategy}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="机器结果"
                value={filters.machine}
                onChange={(value) => updateFilter("machine", value)}
              >
                <option value="all">全部机器结果</option>
                {Object.entries(machineOutcomeLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="人工结果"
                value={filters.manual}
                onChange={(value) => updateFilter("manual", value)}
              >
                <option value="all">全部人工结果</option>
                {Object.entries(manualOutcomeLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="语言"
                value={filters.language}
                onChange={(value) =>
                  updateFilter(
                    "language",
                    value as ProductFilters["language"],
                  )
                }
              >
                <option value="all">全部语言</option>
                <option value="zh-cn">中文 zh-cn</option>
                <option value="en-us">英文 en-us</option>
              </FilterSelect>
              <FilterSelect
                label="证据状态"
                value={filters.binding}
                onChange={(value) => updateFilter("binding", value)}
              >
                <option value="all">全部证据状态</option>
                {Object.entries(bindingLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect
                label="排序"
                value={filters.sort}
                onChange={(value) =>
                  updateFilter("sort", value as ProductFilters["sort"])
                }
              >
                <option value="name_asc">名称 A → Z</option>
                <option value="name_desc">名称 Z → A</option>
                <option value="attention">关注优先</option>
                <option value="category">分类</option>
                <option value="product_key">Product Key</option>
              </FilterSelect>
            </div>
          </div>

          <div className="table-summary" aria-live="polite">
            <p>
              显示 <strong>{formatNumber(filteredProducts.length)}</strong> /{" "}
              {formatNumber(projection.products.length)} 个产品
            </p>
            {JSON.stringify(filters) !== JSON.stringify(defaultFilters) ? (
              <button type="button" onClick={resetFilters}>
                重置全部筛选
              </button>
            ) : null}
          </div>

          {filteredProducts.length > 0 ? (
            <div className="product-table-wrap">
              <table className="product-table">
                <thead>
                  <tr>
                    <th scope="col">产品</th>
                    <th scope="col">分类 / 策略</th>
                    <th scope="col">机器结果</th>
                    <th scope="col">zh-cn</th>
                    <th scope="col">en-us</th>
                    <th scope="col">人工内容检查</th>
                    <th scope="col">证据绑定</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.map((product) => {
                    const manualTone = toneForManual(product.manual_outcome);
                    return (
                      <tr key={product.product_key}>
                        <td data-label="产品">
                          <button
                            className="product-name-button"
                            type="button"
                            onClick={() => openProduct(product.product_key)}
                            data-product-key={product.product_key}
                          >
                            <strong>{product.display_name}</strong>
                            <span className="mono">{product.product_key}</span>
                          </button>
                        </td>
                        <td data-label="分类 / 策略">
                          <span className="table-category">
                            {product.catalog_categories[0]
                              ? (categoryLabels[
                                  product.catalog_categories[0]
                                ] ?? product.catalog_categories[0])
                              : "未分类"}
                          </span>
                          <span className="table-secondary">
                            {strategyLabels[
                              product.semantic_strategy ?? "none"
                            ] ?? product.semantic_strategy}
                          </span>
                        </td>
                        <td data-label="机器结果">
                          <StatusPill
                            compact
                            label={
                              machineOutcomeLabels[product.machine_outcome]
                            }
                            tone={
                              product.machine_outcome === "bilingual_pass"
                                ? "emerald"
                                : product.machine_outcome ===
                                    "single_language_pass"
                                  ? "amber"
                                  : product.machine_outcome ===
                                      "bilingual_fail"
                                    ? "coral"
                                    : "slate"
                            }
                          />
                        </td>
                        {(["zh-cn", "en-us"] as const).map((language) => {
                          const status =
                            product.languages[language].machine.status;
                          const contentGroups =
                            product.languages[language].machine
                              .content_group_count;
                          return (
                            <td data-label={language} key={language}>
                              <span
                                className={`language-result tone-${toneForMachine(status)}`}
                              >
                                <span aria-hidden="true">
                                  {iconForTone(toneForMachine(status))}
                                </span>
                                {status === "pass"
                                  ? `${contentGroups ?? 0} groups`
                                  : status === "fail"
                                    ? "失败"
                                    : "—"}
                              </span>
                            </td>
                          );
                        })}
                        <td data-label="人工内容检查">
                          <StatusPill
                            compact
                            label={manualOutcomeLabels[product.manual_outcome]}
                            tone={manualTone}
                          />
                        </td>
                        <td data-label="证据绑定">
                          <StatusPill
                            compact
                            label={bindingLabels[getBindingFacet(product)]}
                            tone={toneForBinding(getBindingFacet(product))}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <span aria-hidden="true">⌕</span>
              <h3>没有匹配项</h3>
              <p>{emptyStateMessage(filters)}</p>
              <button type="button" onClick={resetFilters}>
                重置筛选
              </button>
            </div>
          )}
        </section>
      </main>

      <footer className="site-footer">
        <div className="shell footer-inner">
          <div>
            <strong>Capability Dashboard</strong>
            <span>
              Projection {projection.schema_version} ·{" "}
              {projection.projection_id}
            </span>
          </div>
          <p>
            机器证据生成于 {formatDate(projection.generated_at)} ·
            人工内容检查不会改变机器结果
          </p>
        </div>
      </footer>

      <ProductDrawer product={selectedProduct} onClose={closeProduct} />
    </>
  );
}
