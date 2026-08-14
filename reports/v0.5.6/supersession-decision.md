# v0.5.6 Supersession Decision

> 状态：**accepted project decision — `superseded before implementation`**
>
> 决策日期：2026-08-13
>
> 决策范围：v0.5.6 Architecture Preflight、Execution Plan 与全部后续实施授权

## 1. 被取代计划的准确身份

| identity | value |
|---|---|
| Plan freeze commit | `7e8ab83bbd58cd6eed1b943bc83ff555c8b229e7` (`docs: freeze v0.5.6 execution plan`) |
| frozen preflight | `reports/v0.5.6/architecture-preflight.md` |
| frozen plan | `plans/v0.5.6-execution-plan.md` |
| accepted functional baseline | annotated tag `v0.5.5` → commit `fdf4461602875fcd97c8556b01118c1114e7c7b3` |
| accepted Batch | `20260813T113000Z-b819c3f2` |
| v0.5.6 implementation at decision time | not started |

原计划拟处理的 repair 6 为：

```text
en-us/postgresql
zh-cn/postgresql
en-us/hpc-cache
zh-cn/hpc-cache
en-us/app-configuration
zh-cn/app-configuration
```

原 repair authority 分别是 F1 unique outermost owner、F2 bounded duplicate suppression、F3 singleton target triangulation，以及 F4 canonical SourceReachability → RegionFilter bridge；计划还拟建立 6 items / 20 scopes 的独立 Evidence 与 Workbench 闭环。

## 2. 新的权威 Source 事实

Plan freeze 后、任何实现前，用户进一步人工核对了上述三个产品的中英文实际页面与 Source HTML，并确认：

1. 当前失败的主要原因不是抽取程序缺少已证明的通用能力；
2. Source 中存在历史遗留结构、异常嵌套、错误或无效控件，以及页面真实行为与 Source 结构不一致；
3. 上游 Source HTML 团队已确认会修改这些 Source；
4. 当前不能把这些异常当成稳定、合法的产品结构并永久编码进抽取器。

这些事实推翻了原计划“repair 6 的当前 Source 能证明通用 extractor repair authority”的核心前提。原 Plan 并非执行失败；它是在实施前因事实前提变化而被取代。

## 3. 决策

v0.5.6 Architecture Preflight 与 Execution Plan 的状态统一为 **`superseded before implementation`**。立即撤销 P1–P6 的全部活动实施授权：

- 不实施 F1、F2 或 F3 Source 容错、纠正或猜测规则；
- 不实施 F4 bridge，不创建 ADR-0092；
- 不创建 v0.5.6 Schema、Profile、Target、reconstruction 或 registry entry；
- 不运行 v0.5.6 formal Batch；
- 不生成或 record v0.5.6 canonical Evidence；
- 不进行 20-scope Workbench review；
- 不升级版本，不创建 `v0.5.6` tag；
- 不创建 v0.6 handoff，不启动 v0.6 planning。

F1/F2/F3 若现在实施，会把已确认将由上游修正的 Source 缺陷固化为长期 production complexity。F4 揭示的 canonical/legacy reader duplication 仍可能是真实架构问题，但它只作为 Repository Rebaseline finding candidate；当前不预设结论，也不授权单独删除、合并或修改 reader。

> 当前决定不证明 F1–F4 在技术上一定错误；它只裁定：在 Source 已确认异常且上游将修复的情况下，没有理由现在为这些异常增加生产复杂度。

## 4. 当前项目状态

```text
Accepted functional baseline:
v0.5.5

v0.5.6 architecture preflight:
superseded before implementation

v0.5.6 execution plan:
superseded before implementation

v0.5.6 production implementation:
not started / not authorized

Current phase:
Repository Rebaseline preparation

v0.6:
blocked / unplanned / unauthorized
```

`v0.5.5` 继续是 accepted functional baseline。v0.5.6 不形成版本号、formal Batch、canonical Evidence 或 tag；原 Plan freeze commit 与文档保留为不可改写的历史决策依据。

## 5. 新 disposition 与重新进入条件

repair 6 的统一 disposition 为 `upstream-source-correction-pending`：owner 是上游 Source HTML 团队；当前系统继续保持可信失败，不生成新 payload，不增加产品特例或通用容错。

accepted Batch `20260813T113000Z-b819c3f2` 逐项确认六项均为 `execution=failed`、`validation=not_run`、`output_path=null`；本裁决保持该 fail-closed 事实，不把失败改写为支持状态。

corrected Source snapshot 到达后也不得直接恢复原 v0.5.6 preflight/plan。重新进入 extraction repair 必须同时满足：

1. Repository Rebaseline 已完成并形成新的 accepted code baseline；
2. 实际页面与 corrected Source 已重新完成人工核对；
3. desktop/mobile controls、真实状态内容与 `soft-category.json` binding 均被重新确认；
4. 问题被重新归因为 Source、Product Definition 或 extraction implementation；
5. 只有在 Source 合法、Product Definition 正确、当前抽取器仍无法正确处理时，才创建新的 architecture preflight；
6. 原 F1/F2/F3、20-scope design 与 329/54 Batch projection 均不自动继承。

Repository Rebaseline 使用 v0.5.5 accepted code、inputs、Batch 与 Evidence；期间不得混入 corrected PostgreSQL、HPC Cache、App Configuration 或 Firewall Manager Source，以避免代码变化和 Source 输入变化同时发生。
