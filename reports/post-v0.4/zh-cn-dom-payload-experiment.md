# 中文四产品 DOM 与 CMS payload 对比实验

- 日期：2026-08-08
- 运行目录：`output/experiments/v0.5.0-independent-fidelity/20260808T135833Z/`
- 语言：仅 `zh-cn`
- 结论：**本次实验通过；4 个产品的 19 个目标片段全部与当前抽取结果完全一致。**

## 做了什么

1. 使用当前 `cli.py extract` 分别生成 `service-bus`、`api-management`、`app-service` 和 `sla-virtual-machines` 的中文 CMS payload。
2. 独立读取 `data/prod-html/zh-cn/` 下的冻结 HTML，不调用生产抽取策略、协调器或内容组装代码。
3. 从桌面版控件读取默认状态和可选状态。`app-service` 的移动地区控件仍保留原样；重复默认项被忽略，没有修改源 HTML。
4. 对可以直接定位的内容使用源 HTML；对地区内容明确加入 `soft-category.json`，按“软件 + 地区”删除不适用表格。
5. 将独立得到的片段与 `baseContent`、`contentGroups[].content` 或 `mainContent` 逐项比较。
6. 在内存中交换 API Management 两个地区的 payload 内容，检查独立比较是否会发现内容放错状态。原 payload 文件没有被修改。

## 结果

| 产品 | 当前抽取 | 状态/片段数 | 原始字符串一致 | DOM 归一后一致 | 定位依据 |
|---|---:|---:|---:|---:|---|
| `service-bus` | 通过 | 1 | 1/1 | 1/1 | 仅源 HTML |
| `api-management` | 通过 | 5 | 5/5 | 5/5 | 源 HTML + `soft-category.json` |
| `app-service` | 通过 | 12 | 12/12 | 12/12 | 源 HTML + `soft-category.json` |
| `sla-virtual-machines` | 通过 | 1 | 1/1 | 1/1 | 仅源 HTML，另执行允许的站内链接改写 |
| **合计** | **4/4** | **19** | **19/19** | **19/19** | — |

受控错误结果：交换 `api-management` 的 `east-china` 与 `east-china2` 内容后，两个错误状态都被发现。

## DOM 能直接证明什么

- `service-bus` 的页面主体可以直接定位，对应 `baseContent`。
- `sla-virtual-machines` 可以从首个 `h2` 定位到文章结尾，对应 `mainContent`。
- `app-service` 的 Windows/Linux 控件分别直接指向 `#tabContent1` 和 `#tabContent2`。
- 两个地区型页面都能从桌面控件读取地区列表，但地区链接只指向按钮，不直接指向内容面板。
- 因此，仅靠 HTML DOM 不能证明“某地区应保留哪些表格”；逐地区比较必须把 `soft-category.json` 作为明确输入。

## App Service 默认地区处理

中文源 HTML 的桌面控件明确选择 `east-china3`，移动控件同时标记了 `east-china3` 和 `east-china2`。按照已确认的“桌面版为准”规则：

- 默认地区采用 `east-china3`；
- 移动版重复默认项不参与默认地区判断，也不单独产生警告；
- 移动版标签与桌面版不一致继续保留 `responsive_filter_label_drift` 警告；
- 桌面版自身不明确时仍停止抽取。

修正后，`app-service` 中文抽取生成 12 个内容组并通过现有验证。

## 输入身份

| 输入 | SHA-256 |
|---|---|
| `service-bus` 源 HTML | `72c8ff0a1a64e9a29e91b32cf0b463269f3fd9dc662e1ec064b3bdab0d1d3d32` |
| `api-management` 源 HTML | `2ff654ac44611f422bdcc7113fba03b7293a1f4c1f2e51b118db8568e7eb45b4` |
| `app-service` 源 HTML | `3f741be65e33792cb19ddbb4e9affb42c3b39b2526da6d2e1c799ea21fc7c0f7` |
| `sla-virtual-machines` 源 HTML | `06df10bc2c2d264e91fdbd0445aa7016833e0f3e9ce3e5dfb258d5ec00c39748` |
| `soft-category.json` | `246ff13a504281d0b0cc23a581d8bd30582e6c1c242b57e3f2848e05e0c6d218` |

逐 payload 哈希、逐状态哈希和源/产物片段保存在本次运行目录的 `comparison/report.json` 与 `comparison/fragments/` 中。

## 这次实验没有证明什么

- 没有访问线上网站，也没有验证当前线上 JavaScript 的行为。
- 没有验证 CSS、图标字体、CMS 模板或最终页面显示效果；例如机器内容一致仍不等于人工审核必然通过。
- 没有覆盖英文页面、其他复杂页结构或整个产品目录。
- 没有完成路线图中完整的 v0.5.0 探索关口；正式结论仍需绑定未来接受的 v0.4.1 Batch，并补齐更广的代表样例。

## 建议

这四个样例已经证明独立内容核对在技术上可行，建议继续推进，但要保持两种证据边界：

1. DOM 能直接定位的内容，记录精确节点和源片段哈希；
2. 地区内容同时记录 `soft-category.json` 哈希、状态身份以及实际删除的表格 ID；
3. 下一轮使用接受后的 v0.4.1 持久化 payload 重跑，而不是把本次临时输出当作正式验收证据；
4. 再补一个带类别页签的复杂页面和一个含历史链接转换的 SLA 页面，然后决定正式核对器的最小范围。

可重复运行的程序与说明位于 `experiments/v0.5.0-independent-fidelity/`。
