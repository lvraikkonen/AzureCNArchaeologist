# M3 Databricks 英文输入笔误修正

> 日期：2026-08-14
>
> 状态：等待上游后续快照正式修正

## 修正原因

英文 Databricks HTML 将同一个表格容器和表格的名称写成：

```text
databricks-Compute-Photon-Job-NCas_T4_v
```

可信 `soft-category.json`、表格标题 `NCas_T4_v3 series` 以及用户确认的正确名称均为：

```text
databricks-Compute-Photon-Job-NCas_T4_v3
```

用户已确认这是上游笔误，并会向上游团队报告。本地上游快照中的两个名称据此直接修正，再由 `source_input` 重新固定到 `data/prod-html/`。

## 实现边界

- 程序中不增加截断名称匹配、前缀匹配或其他特殊猜测；
- 后续上游快照仍必须提供与配置完全相同的表格名称；
- 如果新快照再次出现不一致，输入或抽取应明确阻断；
- 本记录不改变其他产品或其他 HTML 内容。

## 另一个未修改的上游标记

同一英文文件的正文是英文，参考 Product Definition 也明确把它定位为 `en-us` 源路径，但文件中的 `<body class>` 仍是 `zh-cn`。

本次没有修改这个标记。处理语言由已经选定的双语处理项决定，不通过正文内容猜测；Databricks 的状态定位也不使用这个 class。该事实保留在验收记录中，便于上游后续一并核对。
