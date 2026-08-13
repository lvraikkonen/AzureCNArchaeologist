# v0.5.5 Acceptance Status

> 状态：`candidate_awaiting_human_review`

## 当前结论

**机器与证据候选门禁已通过；人工验收尚未发生。** P0–P4 implementation 与 clean-producer gates 已完成，替代正式 Batch、全量 comparison、repair 4 + witness 2 canonical Evidence、immediate verify、second-record 幂等性和 Workbench GET-only readiness 均通过。当前 human reviewed / total 为 **0/6**，因此不得把 v0.5.5 标记为 accepted，不得进入 P6 版本/tag 收口。

| 维度 | 当前状态 | 含义 |
|---|---|---|
| implementation | `passed` | clean producer `55f8c5d…` 通过完整 P4 |
| formal Batch | `passed_with_expected_item_failures` | 434/383 分母不变，323/60/322/1 精确命中冻结预期 |
| Batch comparison | `passed_candidate` | 319/319 retained payload exact bytes；唯一 delta 是 repair 4 |
| repair Evidence | `4/4 passed_current` | Profile 1.2，四个独立 full-content scopes |
| witness Evidence | `2/2 passed_current` | Profile 1.1，双语 `service-bus` S1 scopes |
| second record | `6/6 existing-current/read-only` | 30 files byte inventory 未改变 |
| Workbench reader | `6/6 readable` | GET-only view 每项 1 个 passed scope |
| human review | `0/6 pending` | 需要用户实际检查并明确接受 |
| Machine Gate | `parallel_only`, `runtime_effective=false` | 本版不激活 |

## Formal candidate identity

- Producer：`55f8c5d6faa29587ee899f1fff2aabd687750c34`；
- Batch：`20260813T113000Z-b819c3f2`；
- Input Manifest：`d25683cffb287fbd50a997b90e28d2d340e7fe1c527b5c1255963e2fabc55092`；
- Batch Manifest revision/SHA：1487 / `422c140ad3d71f9ed2b32be2dff0b5e3886ef8e2fbf54db16815042609e3bed7`；
- Batch status：`completed_with_failures`，434 total / 383 runnable / 323 execution-succeeded / 60 execution-failed / 322 validation-passed / 1 validation-failed；
- active Validation Profile：1.4 `e3d0b3aa75c5c6afc76dc75f82b8602dd186aba7a18671a77ebe760e79970388`；
- Pipeline Validation：2.2 `e4868569fdf7487ba506fdf98926e404506ed1152dbc2128439b94ae53b016d2`。

Producer provenance 同时精确绑定两套 target/Profile：

| Artifact | SHA-256 |
|---|---|
| `data/configs/independent-fidelity-targets/v0.5.5-simple-page-global-repair.json` | `0d116ee71ca9a90249c5ce3da5041a20febd6cd8152fb74a9c0290b519014fe2` |
| `data/configs/independent-fidelity-profiles/v0.5.5-simple-page-global.json` | `1d2bb8a3f12a39f6a4cc881595c653406dca24e8ea2feaa8bcbd87da48c03520` |
| `data/configs/independent-fidelity-targets/v0.5.3.json` | `f5350ab26ff002cbf14ed5fbb8fd7405cb392da53fd5717016825a7f19a18432` |
| `data/configs/independent-fidelity-profiles/v0.5.3-four-family.json` | `6a3c6c0fcb93105e2540a88229c302317ae48b4b5d8ea2a1fcf75f196b029f0c` |

Repair 与 witness routing 已由正式 binder 证明唯一、互斥，六项 L3a 均为 passed。

## 待人工复核的 6 个 exact scopes

### Repair — Profile 1.2

| Item | Semantic identity | Artifact SHA-256 | Path |
|---|---|---|---|
| `zh-cn/service-fabric` | `75ebf5142c7b4947882f03ef2bea3cd22ea17e95b87c82b369f1d76451f35dec` | `72a3f614639fe381bc5efb534a597d80d211d2ee522851e9957b7a070970daa8` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/zh-cn/pricing/service-fabric/evidence.json` |
| `en-us/service-fabric` | `add2d10025da4d08fea1b77fe8014c3850d6e4838c090da0a232f5067729cff4` | `6f4b057f0c4ed84dcad97dbd8256c8a4c648d974196d50a3d7bbbcd8a0455dda` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/en-us/pricing/service-fabric/evidence.json` |
| `zh-cn/azure-defender` | `864646760a3762f2275b27a0eb16a93696848e5d5ec02efcfe97e5e60aeda175` | `14b6315d8c7ab0e3fa410e888f7e2a0a6771a0a9ee78b2f9c1f6e48b6faf6c49` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/zh-cn/pricing/azure-defender/evidence.json` |
| `en-us/azure-defender` | `aa77efd8de7b2b7a41b60201b9434065ebaa52e1af7a7c7231d40d5483bb29b8` | `0a73472172ae7e8235b9fd2f6685341c544e6a0b755751108e7a93236d9a1ac9` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/en-us/pricing/azure-defender/evidence.json` |

### S1 witnesses — Profile 1.1

| Item | Semantic identity | Artifact SHA-256 | Path |
|---|---|---|---|
| `zh-cn/service-bus` | `890546de644e6efc091ea39282aa560da660afb2113f07b562f8e627082fc820` | `832882bfd0998721f13f34c1a7a61d1f349f9b8e74b38cf7e5c1c366ee5a472f` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/zh-cn/pricing/service-bus/evidence.json` |
| `en-us/service-bus` | `18b536fccc53821179fcce64e3387bd0d4d5da1bdabe76958119e8890917887a` | `8ebcdb540b397c098d213e8dcc8e4788a15ca55acaf376e7eeaf0144d479e376` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/en-us/pricing/service-bus/evidence.json` |

每项 coverage 均为 1/1/1/0/0。六个 bundles 的 aggregate byte digest 为 `981c0a7a09e43d36f2efc4cffec5406b7bc32404554c6ac5e144556063f9bc9b`。

## 人工接受清单

用户需要在 Workbench 对 6/6 scopes 只读检查，并明确接受：

1. 上述 Batch/producer/Input/Batch Manifest exact identities；
2. repair 4 使用 Profile 1.2，witness 2 使用 Profile 1.1，且两套 target membership 不混用；
3. 六个 scope 的 Source / Expected / Payload / Diff、coverage、semantic identities、artifact hashes 与 canonical paths；
4. 319/319 retained Business Payload exact-byte non-regression，以及仅四项 repair status/payload delta；
5. `virtual-wan` 双语 blocker 与 `event-grid` 双语 exclusion 保持不变；
6. v0.5.3 expected-negative 与 v0.5.4 current Evidence 均保持历史 identity/verdict；
7. Machine Gate 不变，且本接受不构成 L4、Release、upload 或 publication。

Workbench 启动命令：

```bash
uv run cli.py pipeline-review-serve \
  --batch-id 20260813T113000Z-b819c3f2 \
  --dashboard-origin http://127.0.0.1:3000

cd dashboard
npm run dev
```

人工接受后才可进入 P6：把 candidate reports 改为 accepted，更新版本/ROADMAP/handoff，提交 acceptance/version commit，在 clean tree 上重跑完整门禁与 v0.5.3/v0.5.4/v0.5.5 Evidence read-only verification，最后创建本地 annotated `v0.5.5` tag。P6 不再次 record。
