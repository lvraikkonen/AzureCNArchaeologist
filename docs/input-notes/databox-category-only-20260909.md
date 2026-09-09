# Data Box 仅 Category 模式（2026-09-09）

用户确认 Data Box 没有可见区域筛选器、软件筛选器隐藏，只有 Data Box / Data Box Disk 两个 Category 页签。已增加配置驱动的 `extraction.complex_mode: "category_only"`，保持 `complex` / `ComplexFilter`，不按产品名分支。

每种语言输出两个 Content Group，仅有 category 条件。隐藏软件选项只定位源正文，隐藏或不存在的区域控件不产生筛选维度，也不查询区域排除映射。要求唯一隐藏软件选项及完整 Category 导航/面板集合；可见软件/区域、缺失目标会阻断。未配置模式的 Complex 继续要求可见区域。

配置已接入 Catalog、抽取器、Payload 校验、独立 L3b、Batch 固定计划、增量定义比较与审核/Workbench。审核使用 Batch 保存的模式，后续配置变化不会重新解释已封存材料。

验证结果：

- [双语实验](../../runs/databox-category-only-20260909-084118-experiment/REPORT.md)：2/2 条目抽取、L3a、L3b 全部通过，0 blocked / failed。
- 新增 24 项测试通过，覆盖正文丢失、缺失页签、可见维度、无区域 DOM、配置合法性和审核固定模式。
- 隔离对照回归：修改后 143 passed / 22 failed；相同输入、已提交代码为 119 passed / 相同 22 failed，无新增失败。日志见实验报告。
- 开发验证时，工作区 `storage-managed-disks` 配置曾含空 `visible_regions`，导致全局 Catalog 拒绝加载。Data Box 实验仅在副本中缩小目录和 Scope；对照回归仅在临时副本使用该无关配置的已提交版本，未修改用户的 Managed Disks 配置。
- `current_prod_html` 全目录 SHA-256 前后相同；正式 Scope、全局 Frozen HTML、data/state 均未改写。

本轮未创建人工批准、Release 或上传。历史区域版本的批准仅属于历史产物，当前仅 Category 版本仍需新人工审核。

后续用户已调整 Managed Disks 区域规则，配置加载恢复正常。[最终正式范围全量实验](../../runs/pricing-full-recheck-20260909-085013-experiment/REPORT.md)覆盖 99 个 Pricing 产品、198 个语言条目，抽取及 L3a/L3b 全部通过，0 blocked / failed；排除 `batch`、`storage-blobs`、`storage-files`。本次代码提交包含已验证的产品配置调整，人工修改的源 HTML 保留在工作区，未随代码提交。
