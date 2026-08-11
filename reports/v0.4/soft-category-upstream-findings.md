# v0.4 soft-category 上游配置审计与建议

本报告只盘点配置，不修改 `soft-category.json`。重复 exact `(software, region)` 在来源页面证明可达时由严格 projector 在生成 Payload 前阻断，且禁止自动合并。单个 row 内重复 tableID 属于 nonblocking redundancy：运行时按物理首现顺序生成 ordered-unique 投影，同时保留配置卫生 finding。

## 配置身份

- 报告状态：`nonblocking_configuration_hygiene_findings`
- 路径：`data/configs/soft-category.json`
- 大小：346637 bytes
- SHA-256：`3c930c6e163f27bbbbc4e44c8597feb3d112518ffcc309ee5b7bc007978f02d8`
- 配置 entry：325

## 汇总

- 重复 `(software, region)` pair：0，涉及 0 个 entry（blocking）
- row 内重复 tableID：38 个 entry，310 个不同重复 ID，321 个多余 occurrence（nonblocking redundancy）

## 重复 `(software, region)`

| Software | Region | Entry indexes | 跨 entry 重复 tableID 数 |
| --- | --- | --- | ---: |

## row 内重复 tableID

| Entry | Software | Region | 重复 ID 数 | 多余 occurrence |
| ---: | --- | --- | ---: | ---: |
| 0 | `Windows` | `north-china2` | 1 | 1 |
| 1 | `Windows` | `north-china` | 1 | 1 |
| 4 | `Windows` | `north-china3` | 1 | 1 |
| 6 | `Linux` | `north-china2` | 2 | 2 |
| 7 | `Linux` | `north-china` | 3 | 3 |
| 8 | `Linux` | `east-china2` | 2 | 2 |
| 9 | `Linux` | `east-china` | 8 | 9 |
| 10 | `Linux` | `east-china3` | 1 | 1 |
| 11 | `Linux` | `north-china3` | 1 | 1 |
| 13 | `SQL Server for Windows` | `north-china` | 1 | 1 |
| 14 | `SQL Server for Windows` | `east-china2` | 2 | 2 |
| 15 | `SQL Server for Windows` | `east-china` | 2 | 2 |
| 16 | `SQL Server for Windows` | `east-china3` | 27 | 30 |
| 17 | `SQL Server for Windows` | `north-china3` | 27 | 30 |
| 18 | `SQL Server Ubuntu Linux` | `north-china2` | 5 | 5 |
| 22 | `SQL Server Ubuntu Linux` | `north-china3` | 16 | 18 |
| 23 | `SQL Server Ubuntu Linux` | `east-china3` | 16 | 18 |
| 28 | `Machine Learning Server` | `east-china3` | 19 | 19 |
| 29 | `Machine Learning Server` | `north-china3` | 19 | 19 |
| 31 | `SUSE Linux Enterprise Basic` | `north-china` | 2 | 2 |
| 34 | `SUSE Linux Enterprise Basic` | `north-china3` | 30 | 30 |
| 35 | `SUSE Linux Enterprise Basic` | `east-china3` | 30 | 30 |
| 37 | `SUSE Linux Enterprise Server for SAP Priority` | `north-china` | 2 | 2 |
| 40 | `SUSE Linux Enterprise Server for SAP Priority` | `east-china3` | 29 | 29 |
| 41 | `SUSE Linux Enterprise Server for SAP Priority` | `north-china3` | 29 | 29 |
| 44 | `Cloud Services` | `north-china2` | 1 | 1 |
| 45 | `Cloud Services` | `north-china` | 1 | 1 |
| 46 | `Cloud Services` | `east-china2` | 1 | 1 |
| 47 | `Cloud Services` | `east-china` | 1 | 1 |
| 52 | `Elastic Database` | `east-china` | 17 | 17 |
| 53 | `Elastic Database` | `north-china` | 1 | 1 |
| 58 | `Elastic Database` | `east-china2` | 1 | 1 |
| 59 | `Elastic Database` | `north-china2` | 1 | 1 |
| 113 | `Storage Blobs` | `north-china` | 3 | 3 |
| 115 | `Storage Blobs` | `east-china2` | 1 | 1 |
| 116 | `Storage Blobs` | `east-china` | 3 | 3 |
| 287 | `Page Blobs` | `east-china3` | 1 | 1 |
| 288 | `Page Blobs` | `north-china3` | 2 | 2 |

### Entry 0: Windows / north-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table1-r2-4`：2 次，tableIDs indexes = 83, 116
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 1: Windows / north-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vms-table1-3-1`：2 次，tableIDs indexes = 126, 129
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 4: Windows / north-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table1-r2-1`：2 次，tableIDs indexes = 26, 36
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 6: Linux / north-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table1-linux-r2-4-north3`：2 次，tableIDs indexes = 42, 61
- `#vm-table1-linux-r2-4-east3`：2 次，tableIDs indexes = 69, 88
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 7: Linux / north-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table1-linux-r2-4-north3`：2 次，tableIDs indexes = 68, 87
- `#vm-table1-linux-r2-4-east3`：2 次，tableIDs indexes = 95, 114
- `#vm-table-mdsv2-l-n3-1`：2 次，tableIDs indexes = 54, 242
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 8: Linux / east-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table1-linux-r2-4-north3`：2 次，tableIDs indexes = 37, 59
- `#vm-table1-linux-r2-4-east3`：2 次，tableIDs indexes = 67, 86
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 9: Linux / east-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table1-linux-r2-4-north3`：2 次，tableIDs indexes = 66, 88
- `#vm-table1-linux-r2-4-east3`：2 次，tableIDs indexes = 96, 115
- `#vm-table2-3-1-ml`：3 次，tableIDs indexes = 156, 180, 204
- `#vm-table-linux-computingprioritization-f1-f16-region2-ml-enterprise`：2 次，tableIDs indexes = 200, 214
- `#vm-table-linux-computingprioritization-f1-f16-ml-enterprise`：2 次，tableIDs indexes = 201, 215
- `#vm-table-linux-computingprioritization-f1-f16-region2-ml-basic`：2 次，tableIDs indexes = 176, 216
- `#vm-table-linux-computingprioritization-f1-f16-ml-basic`：2 次，tableIDs indexes = 177, 217
- `#vm-table1-ev5-ls-n3`：2 次，tableIDs indexes = 46, 241
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 10: Linux / east-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table1-linux-r2-4-north3`：2 次，tableIDs indexes = 35, 54
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 11: Linux / north-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table1-linux-r2-4-east3`：2 次，tableIDs indexes = 14, 35
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 13: SQL Server for Windows / north-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-sqlserverforwindows-memoryprioritization-ev3-region2`：2 次，tableIDs indexes = 4, 29
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 14: SQL Server for Windows / east-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-sqlserverwindows-memoryprioritization-d15v2`：2 次，tableIDs indexes = 2, 7
- `#vm-table-sqlserverwindows-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 3, 8
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 15: SQL Server for Windows / east-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table3-3-2`：2 次，tableIDs indexes = 3, 10
- `#vm-sqlserverforwindows-memoryprioritization-ev3-region2`：2 次，tableIDs indexes = 2, 49
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 16: SQL Server for Windows / east-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table3-3-2`：2 次，tableIDs indexes = 3, 10
- `#vm-sqlserverforwindows-memoryprioritization-ev3-region2`：3 次，tableIDs indexes = 2, 49, 91
- `#vm-table-sqlserverwindows-memoryprioritization-d15v2`：3 次，tableIDs indexes = 4, 73, 78
- `#vm-table-sqlserverwindows-memoryprioritization-ds15v2`：3 次，tableIDs indexes = 5, 74, 79
- `#vm-table3-1-1-ml`：2 次，tableIDs indexes = 38, 80
- `#vm-table3-1-2-ml`：2 次，tableIDs indexes = 39, 81
- `#vm-table3-1-3-ml`：2 次，tableIDs indexes = 40, 82
- `#vm-table3-1-4-ml`：2 次，tableIDs indexes = 41, 83
- `#vm-table3-1-5-ml`：2 次，tableIDs indexes = 42, 84
- `#vm-table3-1-6-ml`：2 次，tableIDs indexes = 43, 85
- `#vm-table3-1-7-ml`：2 次，tableIDs indexes = 44, 86
- `#vm-table3-1-8-ml`：2 次，tableIDs indexes = 45, 87
- `#vm-table3-1-9-ml`：2 次，tableIDs indexes = 46, 88
- `#vm-table-sqlwindows-computingprioritization-f2sv2-f72sv2-ml`：2 次，tableIDs indexes = 47, 89
- `#vm-table-sqlwindows-computingprioritization-f1-f16-ml`：2 次，tableIDs indexes = 48, 90
- `#vm-table3-2-1-ml`：2 次，tableIDs indexes = 50, 92
- `#vm-table3-3-1-ml`：2 次，tableIDs indexes = 51, 93
- `#vm-sqlserverforwindows-memoryprioritization-ev3-region2-ml`：2 次，tableIDs indexes = 52, 94
- `#vm-table3-3-2-ml`：2 次，tableIDs indexes = 53, 95
- `#vm-table3-3-3-ml`：2 次，tableIDs indexes = 54, 96
- `#vm-table3-3-4-ml`：2 次，tableIDs indexes = 55, 97
- `#vm-table-sqlserverwindows-memoryprioritization-d15v2-ml`：2 次，tableIDs indexes = 56, 98
- `#vm-table3-3-5-ml`：2 次，tableIDs indexes = 57, 99
- `#vm-table-sqlserverwindows-memoryprioritization-ds15v2-ml`：2 次，tableIDs indexes = 58, 100
- `#vm-table-sqlserverwindows-memoryprioritization-mseries-ml`：2 次，tableIDs indexes = 59, 101
- `#vm-table3-4-1-ml`：2 次，tableIDs indexes = 60, 102
- `#vm-table-Constrained-3-3`：2 次，tableIDs indexes = 70, 104
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 17: SQL Server for Windows / north-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table3-3-2`：2 次，tableIDs indexes = 3, 10
- `#vm-sqlserverforwindows-memoryprioritization-ev3-region2`：3 次，tableIDs indexes = 2, 49, 91
- `#vm-table-sqlserverwindows-memoryprioritization-d15v2`：3 次，tableIDs indexes = 4, 73, 78
- `#vm-table-sqlserverwindows-memoryprioritization-ds15v2`：3 次，tableIDs indexes = 5, 74, 79
- `#vm-table3-1-1-ml`：2 次，tableIDs indexes = 38, 80
- `#vm-table3-1-2-ml`：2 次，tableIDs indexes = 39, 81
- `#vm-table3-1-3-ml`：2 次，tableIDs indexes = 40, 82
- `#vm-table3-1-4-ml`：2 次，tableIDs indexes = 41, 83
- `#vm-table3-1-5-ml`：2 次，tableIDs indexes = 42, 84
- `#vm-table3-1-6-ml`：2 次，tableIDs indexes = 43, 85
- `#vm-table3-1-7-ml`：2 次，tableIDs indexes = 44, 86
- `#vm-table3-1-8-ml`：2 次，tableIDs indexes = 45, 87
- `#vm-table3-1-9-ml`：2 次，tableIDs indexes = 46, 88
- `#vm-table-sqlwindows-computingprioritization-f2sv2-f72sv2-ml`：2 次，tableIDs indexes = 47, 89
- `#vm-table-sqlwindows-computingprioritization-f1-f16-ml`：2 次，tableIDs indexes = 48, 90
- `#vm-table3-2-1-ml`：2 次，tableIDs indexes = 50, 92
- `#vm-table3-3-1-ml`：2 次，tableIDs indexes = 51, 93
- `#vm-sqlserverforwindows-memoryprioritization-ev3-region2-ml`：2 次，tableIDs indexes = 52, 94
- `#vm-table3-3-2-ml`：2 次，tableIDs indexes = 53, 95
- `#vm-table3-3-3-ml`：2 次，tableIDs indexes = 54, 96
- `#vm-table3-3-4-ml`：2 次，tableIDs indexes = 55, 97
- `#vm-table-sqlserverwindows-memoryprioritization-d15v2-ml`：2 次，tableIDs indexes = 56, 98
- `#vm-table3-3-5-ml`：2 次，tableIDs indexes = 57, 99
- `#vm-table-sqlserverwindows-memoryprioritization-ds15v2-ml`：2 次，tableIDs indexes = 58, 100
- `#vm-table-sqlserverwindows-memoryprioritization-mseries-ml`：2 次，tableIDs indexes = 59, 101
- `#vm-table3-4-1-ml`：2 次，tableIDs indexes = 60, 102
- `#vm-table-Constrained-3-3`：2 次，tableIDs indexes = 70, 104
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 18: SQL Server Ubuntu Linux / north-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-sqllinux-computingprioritization-f1-f16`：2 次，tableIDs indexes = 4, 19
- `#vm-table4-2-1`：2 次，tableIDs indexes = 5, 21
- `#vm-table4-3-1`：2 次，tableIDs indexes = 1, 22
- `#vm-table-sqlserverlinux-memoryprioritization-d15v2`：2 次，tableIDs indexes = 2, 24
- `#vm-table-sqlserverlinux-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 3, 26
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 22: SQL Server Ubuntu Linux / north-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-sqllinux-computingprioritization-f1-f16`：2 次，tableIDs indexes = 4, 19
- `#vm-table4-2-1`：2 次，tableIDs indexes = 5, 21
- `#vm-table4-3-1`：2 次，tableIDs indexes = 1, 22
- `#vm-table-sqlserverlinux-memoryprioritization-d15v2`：3 次，tableIDs indexes = 2, 24, 31
- `#vm-table-sqlserverlinux-memoryprioritization-ds15v2`：3 次，tableIDs indexes = 3, 26, 32
- `#vm-table4-2-1-region2`：2 次，tableIDs indexes = 20, 34
- `#vms-table-sqlserverlinux-memoryprioritization-d15v2`：2 次，tableIDs indexes = 8, 35
- `#vms-table-sqlserverlinux-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 9, 36
- `#vm-table4-1-1-ml`：2 次，tableIDs indexes = 12, 39
- `#vm-table4-1-2-ml`：2 次，tableIDs indexes = 13, 40
- `#vm-table4-1-3-ml`：2 次，tableIDs indexes = 14, 41
- `#vm-table4-1-4-ml`：2 次，tableIDs indexes = 15, 42
- `#vm-table4-1-5-ml`：2 次，tableIDs indexes = 16, 43
- `#vm-table4-1-6-ml`：2 次，tableIDs indexes = 17, 44
- `#vm-table-sqllinux-computingprioritization-f1-f16-region2-ml`：2 次，tableIDs indexes = 18, 45
- `#vm-table-Constrained-4-1`：2 次，tableIDs indexes = 28, 63
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 23: SQL Server Ubuntu Linux / east-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-sqllinux-computingprioritization-f1-f16`：2 次，tableIDs indexes = 4, 19
- `#vm-table4-2-1`：2 次，tableIDs indexes = 5, 21
- `#vm-table4-3-1`：2 次，tableIDs indexes = 1, 22
- `#vm-table-sqlserverlinux-memoryprioritization-d15v2`：3 次，tableIDs indexes = 2, 24, 31
- `#vm-table-sqlserverlinux-memoryprioritization-ds15v2`：3 次，tableIDs indexes = 3, 26, 32
- `#vm-table4-2-1-region2`：2 次，tableIDs indexes = 20, 34
- `#vms-table-sqlserverlinux-memoryprioritization-d15v2`：2 次，tableIDs indexes = 8, 35
- `#vms-table-sqlserverlinux-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 9, 36
- `#vm-table4-1-1-ml`：2 次，tableIDs indexes = 12, 39
- `#vm-table4-1-2-ml`：2 次，tableIDs indexes = 13, 40
- `#vm-table4-1-3-ml`：2 次，tableIDs indexes = 14, 41
- `#vm-table4-1-4-ml`：2 次，tableIDs indexes = 15, 42
- `#vm-table4-1-5-ml`：2 次，tableIDs indexes = 16, 43
- `#vm-table4-1-6-ml`：2 次，tableIDs indexes = 17, 44
- `#vm-table-sqllinux-computingprioritization-f1-f16-region2-ml`：2 次，tableIDs indexes = 18, 45
- `#vm-table-Constrained-4-1`：2 次，tableIDs indexes = 28, 63
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 28: Machine Learning Server / east-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table5-3-1`：2 次，tableIDs indexes = 3, 40
- `#vm-table-machinelearning-memoryprioritization-d15v2`：2 次，tableIDs indexes = 5, 41
- `#vm-table-machinelearning-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 6, 42
- `#vms-table5-3-1`：2 次，tableIDs indexes = 12, 45
- `#vms-table-machinelearning-memoryprioritization-d15v2`：2 次，tableIDs indexes = 14, 46
- `#vms-table-machinelearning-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 15, 47
- `#vm-table5-1-1-ml`：2 次，tableIDs indexes = 17, 48
- `#vm-table5-1-2-ml`：2 次，tableIDs indexes = 18, 49
- `#vm-table5-1-3-ml`：2 次，tableIDs indexes = 19, 50
- `#vm-table5-1-4-ml`：2 次，tableIDs indexes = 20, 51
- `#vm-table5-1-5-ml`：2 次，tableIDs indexes = 21, 52
- `#vm-table5-1-6-ml`：2 次，tableIDs indexes = 22, 53
- `#vm-table-machinelearning-computingprioritization-f1-f16-ml`：2 次，tableIDs indexes = 23, 54
- `#vm-table5-2-1-ml`：2 次，tableIDs indexes = 24, 55
- `#vm-table5-3-1-ml`：2 次，tableIDs indexes = 25, 56
- `#vm-table5-3-2-ml`：2 次，tableIDs indexes = 26, 57
- `#vm-table-machinelearning-memoryprioritization-d15v2-ml`：2 次，tableIDs indexes = 27, 58
- `#vm-table5-3-3-ml`：2 次，tableIDs indexes = 28, 59
- `#vm-table-machinelearning-memoryprioritization-ds15v2-ml`：2 次，tableIDs indexes = 29, 60
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 29: Machine Learning Server / north-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table5-3-1`：2 次，tableIDs indexes = 3, 40
- `#vm-table-machinelearning-memoryprioritization-d15v2`：2 次，tableIDs indexes = 5, 41
- `#vm-table-machinelearning-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 6, 42
- `#vms-table5-3-1`：2 次，tableIDs indexes = 12, 45
- `#vms-table-machinelearning-memoryprioritization-d15v2`：2 次，tableIDs indexes = 14, 46
- `#vms-table-machinelearning-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 15, 47
- `#vm-table5-1-1-ml`：2 次，tableIDs indexes = 17, 48
- `#vm-table5-1-2-ml`：2 次，tableIDs indexes = 18, 49
- `#vm-table5-1-3-ml`：2 次，tableIDs indexes = 19, 50
- `#vm-table5-1-4-ml`：2 次，tableIDs indexes = 20, 51
- `#vm-table5-1-5-ml`：2 次，tableIDs indexes = 21, 52
- `#vm-table5-1-6-ml`：2 次，tableIDs indexes = 22, 53
- `#vm-table-machinelearning-computingprioritization-f1-f16-ml`：2 次，tableIDs indexes = 23, 54
- `#vm-table5-2-1-ml`：2 次，tableIDs indexes = 24, 55
- `#vm-table5-3-1-ml`：2 次，tableIDs indexes = 25, 56
- `#vm-table5-3-2-ml`：2 次，tableIDs indexes = 26, 57
- `#vm-table-machinelearning-memoryprioritization-d15v2-ml`：2 次，tableIDs indexes = 27, 58
- `#vm-table5-3-3-ml`：2 次，tableIDs indexes = 28, 59
- `#vm-table-machinelearning-memoryprioritization-ds15v2-ml`：2 次，tableIDs indexes = 29, 60
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 31: SUSE Linux Enterprise Basic / north-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ev3-region2`：2 次，tableIDs indexes = 5, 10
- `#vms-table-suse-linux-enterprise-server-basic-memoryprioritization-ev3-region2`：2 次，tableIDs indexes = 19, 24
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 34: SUSE Linux Enterprise Basic / north-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-d15v2`：2 次，tableIDs indexes = 2, 45
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 3, 46
- `#vms-table-suse-linux-enterprise-server-basic-memoryprioritization-d15v2`：2 次，tableIDs indexes = 9, 56
- `#vms-table-suse-linux-enterprise-server-basic-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 10, 57
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-a0-a4-basic-ml`：2 次，tableIDs indexes = 14, 62
- `#vm-table-suse-linux-enterprise-server-a0-a7-standard-ml`：2 次，tableIDs indexes = 15, 63
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-b1s-b8ms-ml`：2 次，tableIDs indexes = 16, 64
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-a1v2-a8mv2-ml`：2 次，tableIDs indexes = 17, 65
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-d2v3-d64v3-ml`：2 次，tableIDs indexes = 18, 66
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-d2sv3-d64sv3-ml`：2 次，tableIDs indexes = 19, 67
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-d1-d4-ml`：2 次，tableIDs indexes = 20, 68
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-d1v2-d5v2-ml`：2 次，tableIDs indexes = 21, 69
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-ds1v2-ds5v2-ml`：2 次，tableIDs indexes = 22, 70
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-fsv2-ml`：2 次，tableIDs indexes = 23, 71
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-f1-f16-region2-ml`：2 次，tableIDs indexes = 24, 72
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-f1-f16-ml`：2 次，tableIDs indexes = 25, 73
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-f1s-f16s-region2-ml`：2 次，tableIDs indexes = 26, 74
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-f1s-f16s-ml`：2 次，tableIDs indexes = 27, 75
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-e2v3-e64v3-ml`：2 次，tableIDs indexes = 28, 76
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ev3-region2-ml`：2 次，tableIDs indexes = 29, 77
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-e2sv3-e64sv3-ml`：2 次，tableIDs indexes = 30, 78
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-d11-d14-ml`：2 次，tableIDs indexes = 31, 79
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-d11v2-d15v2-ml`：2 次，tableIDs indexes = 32, 80
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-d15v2-ml`：2 次，tableIDs indexes = 33, 81
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ds11v2-ds14v2-ml`：2 次，tableIDs indexes = 34, 82
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ds15v2-ml`：2 次，tableIDs indexes = 35, 83
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-m32ls-m32ts-ml`：2 次，tableIDs indexes = 36, 84
- `#vm-table-suse-linux-enterprise-server-basic-gpu-nc6sv3-nc24rsv3-ml`：2 次，tableIDs indexes = 37, 85
- `#vm-table-Constrained-6-3`：2 次，tableIDs indexes = 39, 95
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-b1s-b8ms`：2 次，tableIDs indexes = 40, 98
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 35: SUSE Linux Enterprise Basic / east-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-d15v2`：2 次，tableIDs indexes = 2, 45
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 3, 46
- `#vms-table-suse-linux-enterprise-server-basic-memoryprioritization-d15v2`：2 次，tableIDs indexes = 9, 56
- `#vms-table-suse-linux-enterprise-server-basic-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 10, 57
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-a0-a4-basic-ml`：2 次，tableIDs indexes = 14, 62
- `#vm-table-suse-linux-enterprise-server-a0-a7-standard-ml`：2 次，tableIDs indexes = 15, 63
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-b1s-b8ms-ml`：2 次，tableIDs indexes = 16, 64
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-a1v2-a8mv2-ml`：2 次，tableIDs indexes = 17, 65
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-d2v3-d64v3-ml`：2 次，tableIDs indexes = 18, 66
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-d2sv3-d64sv3-ml`：2 次，tableIDs indexes = 19, 67
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-d1-d4-ml`：2 次，tableIDs indexes = 20, 68
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-d1v2-d5v2-ml`：2 次，tableIDs indexes = 21, 69
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-ds1v2-ds5v2-ml`：2 次，tableIDs indexes = 22, 70
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-fsv2-ml`：2 次，tableIDs indexes = 23, 71
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-f1-f16-region2-ml`：2 次，tableIDs indexes = 24, 72
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-f1-f16-ml`：2 次，tableIDs indexes = 25, 73
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-f1s-f16s-region2-ml`：2 次，tableIDs indexes = 26, 74
- `#vm-table-suse-linux-enterprise-server-basic-computingoptimization-f1s-f16s-ml`：2 次，tableIDs indexes = 27, 75
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-e2v3-e64v3-ml`：2 次，tableIDs indexes = 28, 76
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ev3-region2-ml`：2 次，tableIDs indexes = 29, 77
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-e2sv3-e64sv3-ml`：2 次，tableIDs indexes = 30, 78
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-d11-d14-ml`：2 次，tableIDs indexes = 31, 79
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-d11v2-d15v2-ml`：2 次，tableIDs indexes = 32, 80
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-d15v2-ml`：2 次，tableIDs indexes = 33, 81
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ds11v2-ds14v2-ml`：2 次，tableIDs indexes = 34, 82
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-ds15v2-ml`：2 次，tableIDs indexes = 35, 83
- `#vm-table-suse-linux-enterprise-server-basic-memoryprioritization-m32ls-m32ts-ml`：2 次，tableIDs indexes = 36, 84
- `#vm-table-suse-linux-enterprise-server-basic-gpu-nc6sv3-nc24rsv3-ml`：2 次，tableIDs indexes = 37, 85
- `#vm-table-Constrained-6-3`：2 次，tableIDs indexes = 39, 95
- `#vm-table-suse-linux-enterprise-server-basic-generalpurpose-b1s-b8ms`：2 次，tableIDs indexes = 40, 98
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 37: SUSE Linux Enterprise Server for SAP Priority / north-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ev3-region2`：2 次，tableIDs indexes = 5, 10
- `#vms-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ev3-region2`：2 次，tableIDs indexes = 19, 24
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 40: SUSE Linux Enterprise Server for SAP Priority / east-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d15v2`：2 次，tableIDs indexes = 2, 45
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 3, 46
- `#vms-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d15v2`：2 次，tableIDs indexes = 9, 56
- `#vms-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 10, 57
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-a0-a4-basic-ml`：2 次，tableIDs indexes = 14, 62
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-a0-a7-standard-ml`：2 次，tableIDs indexes = 15, 63
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-b1s-b8ms-ml`：2 次，tableIDs indexes = 16, 64
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-a1v2-a8mv2-ml`：2 次，tableIDs indexes = 17, 65
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-d2v3-d64v3-ml`：2 次，tableIDs indexes = 18, 66
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-d2sv3-d64sv3-ml`：2 次，tableIDs indexes = 19, 67
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-d1-d4-ml`：2 次，tableIDs indexes = 20, 68
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-d1v2-d5v2-ml`：2 次，tableIDs indexes = 21, 69
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-ds1v2-ds5v2-ml`：2 次，tableIDs indexes = 22, 70
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f2sv2-f72sv2-ml`：2 次，tableIDs indexes = 23, 71
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f1-f16-region2-ml`：2 次，tableIDs indexes = 24, 72
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f1-f16-ml`：2 次，tableIDs indexes = 25, 73
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f1s-f16s-region2-ml`：2 次，tableIDs indexes = 26, 74
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f1s-f16s-ml`：2 次，tableIDs indexes = 27, 75
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-e2v3-e64v3-ml`：2 次，tableIDs indexes = 28, 76
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ev3-region2-ml`：2 次，tableIDs indexes = 29, 77
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-e2sv3-e64sv3-ml`：2 次，tableIDs indexes = 30, 78
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d11-d14-ml`：2 次，tableIDs indexes = 31, 79
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d11v2-d15v2-ml`：2 次，tableIDs indexes = 32, 80
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d15v2-ml`：2 次，tableIDs indexes = 33, 81
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ds11v2-ds14v2-ml`：2 次，tableIDs indexes = 34, 82
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ds15v2-ml`：2 次，tableIDs indexes = 35, 83
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-m32ls-m32ts-ml`：2 次，tableIDs indexes = 36, 84
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-gpu-nc6sv3-nc24rsv3-ml`：2 次，tableIDs indexes = 37, 85
- `#vm-table-Constrained-7-3`：2 次，tableIDs indexes = 39, 95
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 41: SUSE Linux Enterprise Server for SAP Priority / north-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d15v2`：2 次，tableIDs indexes = 2, 45
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 3, 46
- `#vms-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d15v2`：2 次，tableIDs indexes = 9, 56
- `#vms-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ds15v2`：2 次，tableIDs indexes = 10, 57
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-a0-a4-basic-ml`：2 次，tableIDs indexes = 14, 62
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-a0-a7-standard-ml`：2 次，tableIDs indexes = 15, 63
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-b1s-b8ms-ml`：2 次，tableIDs indexes = 16, 64
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-a1v2-a8mv2-ml`：2 次，tableIDs indexes = 17, 65
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-d2v3-d64v3-ml`：2 次，tableIDs indexes = 18, 66
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-d2sv3-d64sv3-ml`：2 次，tableIDs indexes = 19, 67
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-d1-d4-ml`：2 次，tableIDs indexes = 20, 68
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-d1v2-d5v2-ml`：2 次，tableIDs indexes = 21, 69
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-generalpurpose-ds1v2-ds5v2-ml`：2 次，tableIDs indexes = 22, 70
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f2sv2-f72sv2-ml`：2 次，tableIDs indexes = 23, 71
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f1-f16-region2-ml`：2 次，tableIDs indexes = 24, 72
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f1-f16-ml`：2 次，tableIDs indexes = 25, 73
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f1s-f16s-region2-ml`：2 次，tableIDs indexes = 26, 74
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-computingoptimization-f1s-f16s-ml`：2 次，tableIDs indexes = 27, 75
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-e2v3-e64v3-ml`：2 次，tableIDs indexes = 28, 76
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ev3-region2-ml`：2 次，tableIDs indexes = 29, 77
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-e2sv3-e64sv3-ml`：2 次，tableIDs indexes = 30, 78
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d11-d14-ml`：2 次，tableIDs indexes = 31, 79
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d11v2-d15v2-ml`：2 次，tableIDs indexes = 32, 80
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-d15v2-ml`：2 次，tableIDs indexes = 33, 81
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ds11v2-ds14v2-ml`：2 次，tableIDs indexes = 34, 82
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-ds15v2-ml`：2 次，tableIDs indexes = 35, 83
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-memoryprioritization-m32ls-m32ts-ml`：2 次，tableIDs indexes = 36, 84
- `#vm-table-suse-linux-enterprise-server-for-sap-priority-gpu-nc6sv3-nc24rsv3-ml`：2 次，tableIDs indexes = 37, 85
- `#vm-table-Constrained-7-3`：2 次，tableIDs indexes = 39, 95
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 44: Cloud Services / north-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#cloudservice-table-optimizedcompute-memoryintensive-E2v3-E64v3-east3`：2 次，tableIDs indexes = 10, 15
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 45: Cloud Services / north-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#cloudservice-table-optimizedcompute-memoryintensive-E2v3-E64v3-east3`：2 次，tableIDs indexes = 3, 8
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 46: Cloud Services / east-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#cloudservice-table-optimizedcompute-memoryintensive-E2v3-E64v3-east3`：2 次，tableIDs indexes = 3, 8
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 47: Cloud Services / east-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#cloudservice-table-optimizedcompute-memoryintensive-E2v3-E64v3-east3`：2 次，tableIDs indexes = 3, 8
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 52: Elastic Database / east-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#sqldb-elastic-vcore-general-purpose-gen4-n3`：2 次，tableIDs indexes = 33, 49
- `#Managed_Instance_standard-area-2-n3`：2 次，tableIDs indexes = 34, 50
- `#Elastic_General_Storage_9_N3-t`：2 次，tableIDs indexes = 35, 51
- `#elastic_1-1_Point_N3-t`：2 次，tableIDs indexes = 36, 52
- `#elastic_1-1_Long_N3-t`：2 次，tableIDs indexes = 37, 53
- `#Elastic_Database_NE3_4-t`：2 次，tableIDs indexes = 38, 54
- `#Elastic_Business_Critical_Gen5_19_N3-t`：2 次，tableIDs indexes = 39, 55
- `#Elastic_Database_NE3_5-t`：2 次，tableIDs indexes = 40, 56
- `#elastic_1-2_Point_N3-t`：2 次，tableIDs indexes = 41, 57
- `#elastic_1-2_Long_N3-t`：2 次，tableIDs indexes = 42, 58
- `#Elastic_Database_NE3_8-t`：2 次，tableIDs indexes = 43, 59
- `#Elastic_6_Elastic_Pools_Basic_N3-t`：2 次，tableIDs indexes = 44, 60
- `#Elastic_7_Elastic_Pools_Standard_N3-t`：2 次，tableIDs indexes = 45, 61
- `#Elastic_8_Elastic_Pools_Premium_N3-t`：2 次，tableIDs indexes = 46, 62
- `#Elastic_Database_NE3_12-t`：2 次，tableIDs indexes = 47, 63
- `#elastic_1-3_Long_N3-t`：2 次，tableIDs indexes = 48, 64
- `#Elastic_database_N3_2_a`：2 次，tableIDs indexes = 73, 75
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 53: Elastic Database / north-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#Elastic_database_N3_2_a`：2 次，tableIDs indexes = 59, 61
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 58: Elastic Database / east-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#Elastic_database_N3_2_a`：2 次，tableIDs indexes = 52, 54
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 59: Elastic Database / north-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#Elastic_database_N3_2_a`：2 次，tableIDs indexes = 46, 48
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 113: Storage Blobs / north-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#storage-blobs-gpv2-operations-and-data-transfer-prices-hierarchy`：2 次，tableIDs indexes = 9, 19
- `#storage-blobs-gpv2-operations-and-data-transfer-prices-hierarchy2`：2 次，tableIDs indexes = 10, 20
- `#storage-blobs-gpv2-operations-and-data-transfer-prices-hierarchy3`：2 次，tableIDs indexes = 11, 21
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 115: Storage Blobs / east-china2

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#storage-blobs-blob-storage-operation-transfer-east3`：2 次，tableIDs indexes = 23, 44
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 116: Storage Blobs / east-china

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#storage-blobs-gpv2-operations-and-data-transfer-prices-hierarchy`：2 次，tableIDs indexes = 9, 18
- `#storage-blobs-gpv2-operations-and-data-transfer-prices-hierarchy2`：2 次，tableIDs indexes = 10, 19
- `#storage-blobs-gpv2-operations-and-data-transfer-prices-hierarchy3`：2 次，tableIDs indexes = 11, 20
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 287: Page Blobs / east-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#page-blobs-gv1-standard-data-storage`：2 次，tableIDs indexes = 8, 17
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.

### Entry 288: Page Blobs / north-china3

- Finding：`SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW`；`nonblocking_redundancy`；运行时 `ordered_unique_by_first_physical_occurrence`
- `#page-blobs-gv1-premium-addition`：2 次，tableIDs indexes = 0, 7
- `#page-blobs-gv1-standard-data-storage`：2 次，tableIDs indexes = 9, 18
- 上游动作：The runtime already treats repeated normalized table identities as nonblocking redundancy and retains each identity at its first physical occurrence. Upstream may remove later occurrences for configuration hygiene, provided that ordered-unique sequence remains unchanged.
- 修复后检查：
  - The runtime projection equals the normalized tableIDs ordered by physical first occurrence.
  - Any upstream cleanup removes only later duplicate occurrences and preserves the ordered-unique sequence.
  - The exact state is replayed after cleanup and produces the same projection and Payload content.
