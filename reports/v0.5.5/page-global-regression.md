# v0.5.5 Page-Global Regression

> 状态：`candidate_awaiting_human_review`
>
> Formal Batch：`20260813T113000Z-b819c3f2`
>
> Producer：`55f8c5d6faa29587ee899f1fff2aabd687750c34`
>
> Reference Batch：`20260813T013534Z-b9e91703`

## 结论

两个新的显式 Simple boundaries 在 frozen bilingual Sources 上完成生产修复，并由独立 reconstruction 形成 4/4 passed Profile 1.2 Evidence。双语 `service-bus` 继续由历史 Profile 1.1 形成 2/2 passed S1 witnesses。六个 bundles 均 current/hash-valid；immediate verify 与 second-record 幂等检查通过。

固定输入与正式 Batch 两层 comparison 均证明：reference 的 319/319 Business Payload exact byte-identical，只新增四份 repair payload；`virtual-wan` blocker 与 `event-grid` exclusion 精确不变。

## Production boundaries

### S5 — `sole_direct_static_business_wrapper_before_common_sections`

只用于 `service-fabric`。resolver 要求 `pure-content` 下在 exact ProductDescription 与 FAQ/SLA common boundary 之间恰有一个 direct material wrapper；wrapper 无 active controls，retained IDs 非空且 page-global unique。完整 wrapper outer HTML 是唯一 Source fragment，并整体转换为 `baseContent`。

| Language | Normalized/Source SHA-256 | Source fragment SHA-256 | Wire SHA-256 | Payload SHA-256 | `baseContent` chars |
|---|---|---|---|---|---:|
| `zh-cn` | `f0b12ba8e2e984c5b96746c613da2a354be99ee8285cec4186be0d2fc09fe6a2` | `70b0a22305d1b0f247e2cee58316228dc95097738784746c191a292c12044774` | `c3c3545c5ba0d7f89a2e950318a180a40c17c82e90e7cb11843a484d3e0a5709` | `83e3d94021504cfcfd42ae4e6b2321f99fd465114afaed30e47d2c694321c63f` | 1,209 |
| `en-us` | `25ef88c24aacf453a1799bc30fc679816b18e45bd5a0643343ca0f481783e468` | `b713ff78c7c33f0ed4eba52f33abd3ab483855283dc697cc4062de91453234e6` | `d1c2b91607201cad1430c775d20b72da90e5f8de60f762fc3bb10da48e26e839` | `df1ef1ced566eed04b34dcadca946688123bce8d9c7380f6679ca3672ed07108` | 1,762 |

### S6 — `sole_inert_singleton_selector_target_before_common_sections`

只用于 `azure-defender`。desktop 与 mobile control domain 必须各自只有一个 selected identity，且精确指向同一个 selector-owned unique target；selector 内不存在第二 material target 或 reachable dimension。只保留该 target outer HTML，control UI 不进入 `baseContent`。

| Language | Normalized/Source SHA-256 | Source fragment SHA-256 | Wire SHA-256 | Payload SHA-256 | `baseContent` chars |
|---|---|---|---|---|---:|
| `zh-cn` | `877b8e9156774f46b01637072478db9e6370e9dc4ad97dbe83a9cf37fd5b89d0` | `8c54da45436efad13d21e4dc43d4c1761223521762881758049d2b9aca838878` | `bba52ba3d5cd8c271c7664c794d690908df4ea3c2b6f0144e67edb75cbfc39ab` | `a98f636ea6adde37e26654f39b67fb5dff1372673b6091f260e20f8f87867b7b` | 6,311 |
| `en-us` | `166cf8b7be4a57911b1b5dd67fab92c3fc10ba94a4031ca51739e8d3d35671a0` | `52f0906900bfd5471a084cdfbd641feb782afc14a43a6354c39a7fa5e9463e91` | `96a0a041c890f322d6a71d77cf835c479f67424ff2ffca4c1f8001b58c3cb9bc` | `183bad41ab23ebf2ae11ddbb410a35f94b1376a82691b27505c018b1b502fd87` | 9,078 |

四份 payload 均为合法 Simple payload：`pageConfig.pageType=Simple`、filters disabled、`contentGroups=[]`、`baseContent` 非空。

## Successor contract 与门禁

- Product Definition 1.2 只增加 S5/S6 enum；Product Definition 1.1 historical SHA 保持 `57a1fa0c49c07d021da2fed1f0b777fbb7f9534d68076ee35d496a2d2c2e42e4`。
- active Validation Profile 1.4 identity 为 `e3d0b3aa75c5c6afc76dc75f82b8602dd186aba7a18671a77ebe760e79970388`，精确绑定 Pipeline Validation 2.2 `e4868569fdf7487ba506fdf98926e404506ed1152dbc2128439b94ae53b016d2`。
- historical Pipeline Validation 2.1 SHA 仍为 `6a3d842ba5f6e85426c855fdaf334d44b0cda9cf927283a95b7d2f816a3e1ff9`。
- closed routing 为 P3 → 2.0、historical P3-successor → 2.1、Profile 1.4 → 2.2；正式 Batch 的 323 份 validation projections 全部为 2.2，323 份 sampled-content evidence 齐全。
- clean producer P4 通过 `1193 passed, 229 subtests passed`、independence runtime smoke、Core fixture/baseline/determinism、reference/API fidelity、catalog/source/config、Dashboard lint/tests、lock 与 clean-tree gates。
- historical v0.5.3 expected-nonzero 仍精确 exit 2；v0.5.4 三项 current Evidence 均保持原 identity 与 passed verdict。

## Repair Evidence — Profile 1.2 / target set `v0.5.5-simple-page-global-repair`

全部 scope 为 `full_content`，payload locator 为 `baseContent`，coverage 为 required/completed/passed/failed/blocked。

| Item | Coverage | Semantic identity | Evidence artifact SHA-256 | Canonical path |
|---|---:|---|---|---|
| `zh-cn/service-fabric` | 1/1/1/0/0 | `75ebf5142c7b4947882f03ef2bea3cd22ea17e95b87c82b369f1d76451f35dec` | `72a3f614639fe381bc5efb534a597d80d211d2ee522851e9957b7a070970daa8` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/zh-cn/pricing/service-fabric/evidence.json` |
| `en-us/service-fabric` | 1/1/1/0/0 | `add2d10025da4d08fea1b77fe8014c3850d6e4838c090da0a232f5067729cff4` | `6f4b057f0c4ed84dcad97dbd8256c8a4c648d974196d50a3d7bbbcd8a0455dda` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/en-us/pricing/service-fabric/evidence.json` |
| `zh-cn/azure-defender` | 1/1/1/0/0 | `864646760a3762f2275b27a0eb16a93696848e5d5ec02efcfe97e5e60aeda175` | `14b6315d8c7ab0e3fa410e888f7e2a0a6771a0a9ee78b2f9c1f6e48b6faf6c49` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/zh-cn/pricing/azure-defender/evidence.json` |
| `en-us/azure-defender` | 1/1/1/0/0 | `aa77efd8de7b2b7a41b60201b9434065ebaa52e1af7a7c7231d40d5483bb29b8` | `0a73472172ae7e8235b9fd2f6685341c544e6a0b755751108e7a93236d9a1ac9` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/en-us/pricing/azure-defender/evidence.json` |

Profile：`v0.5.5-independent-fidelity-simple-page-global` / schema 1.2；reconstruction：`independent-simple-page-global-reconstruction-v2`。

## S1 Witness Evidence — Profile 1.1 / target set `v0.5.3-four-family-core-and-carry-over`

| Item | Coverage | Semantic identity | Evidence artifact SHA-256 | Canonical path |
|---|---:|---|---|---|
| `zh-cn/service-bus` | 1/1/1/0/0 | `890546de644e6efc091ea39282aa560da660afb2113f07b562f8e627082fc820` | `832882bfd0998721f13f34c1a7a61d1f349f9b8e74b38cf7e5c1c366ee5a472f` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/zh-cn/pricing/service-bus/evidence.json` |
| `en-us/service-bus` | 1/1/1/0/0 | `18b536fccc53821179fcce64e3387bd0d4d5da1bdabe76958119e8890917887a` | `8ebcdb540b397c098d213e8dcc8e4788a15ca55acaf376e7eeaf0144d479e376` | `runs/20260813T113000Z-b819c3f2/independent-fidelity/en-us/pricing/service-bus/evidence.json` |

Profile：`v0.5.3-independent-fidelity-four-family` / schema 1.1；reconstruction：`independent-four-family-reconstruction-v1`。该 witness 没有被复制进 Profile 1.2 target set。

## Idempotence 与 Workbench readiness

- immediate verify：repair 4/4 与 witness 2/2 全部 `canonical_bundle_verified`；
- second record：六项全部 `existing_current_bundle_verified` / `existing-current/read-only`；
- 六个 closed-world bundles 共 30 files；second-record 前后 aggregate byte digest 均为 `981c0a7a09e43d36f2efc4cffec5406b7bc32404554c6ac5e144556063f9bc9b`；
- Workbench 真实 GET-only reader 已读取 6/6 views，每项恰有 1 个 passed scope；未写 L4 Review Decision。

## Claim boundary

这些结果证明四项 S5/S6 repair 与双语 S1 witness 对当前 frozen Source、Product Definition、payload 和 producer binding 的独立内容一致性。它不证明全部 Simple catalog 都已有 L3b，不解除 `virtual-wan` / `event-grid`，不激活 Machine Gate，也不构成 L4、Release 或 publication acceptance。
