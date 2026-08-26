# Azure Blob Release 发布规格

> 状态：已实现本地 Release 到 Azure Blob 的发布能力
>
> 日期：2026-08-26

## 1. 目的与边界

Blob 发布位于人工审核和本地 Release 封存之后。它只负责把一个已经通过 `release-verify` 的 Release 交付给 CMS，不参与抽取、机器检查、人工决定或 Release 产品选择。

完整 Release 和 Delta Release 使用同一个上传入口。上传范围始终来自指定 Release 自己的 `products[].items[]`：

- 完整 Release 上传该 Release 中全部已批准产品；
- Delta Release 只上传该 Release 中包含的增量批准产品；
- 不接受额外 Product Key，也不会扫描其他 Release 或普通输出目录；
- 不上传 `review-decisions/`、本机 `release-manifest.json` 或审核引用链。

## 2. Blob 目录

目标容器内使用“上传日期 / Release ID”两级前缀：

```text
{container}/
└── YYYY-MM-DD/                         本机执行上传时的日期
    └── {release-id}/                   Release ID 自身保留时间戳
        ├── payloads/
        │   ├── zh-cn/...
        │   └── en-us/...
        └── delivery-manifest.json      本次目录的完成标志
```

如果同一天有多个 Release，它们位于同一个日期前缀下的不同 `release-id` 目录。CMS 可按 Release ID 中的时间戳判断更新顺序；后续日期的增量 Release 放到实际上传日对应的新日期前缀中。

上游内容变化不会覆盖历史 Blob。产品重新处理、审核和 Release 后，会通过新的 Release ID 产生一份新 Payload；历史交付继续保留。当前没有产品下线或删除语义。

## 3. 完成标志与失败边界

程序按以下顺序发布：

1. 重新执行本地 `release-verify`；
2. 按 Release 清单顺序上传全部 Payload；
3. 全部 Payload 成功后，最后上传 `delivery-manifest.json`。

CMS 只能消费包含 `delivery-manifest.json` 的 Release 目录。任一 Payload 上传失败时，程序立即停止，不会写入 manifest；因此网络错误或进程中断留下的部分目录不是可消费交付。

所有 Blob 都使用不覆盖写入。相同 Blob 路径已经存在时，上传失败并报告具体路径；当前不实现跳过已有文件、重复上传、自动清理部分目录或覆盖重试。

目标容器必须由运维预先创建。程序不会凭连接串自动创建容器或修改容器权限。

## 4. Delivery Manifest 合同

`delivery-manifest.json` 使用 UTF-8 JSON，当前 `schema_version` 为 `1.0`。它只包含 CMS 消费和交付追踪所需的信息：

```json
{
  "schema_version": "1.0",
  "release_id": "release-20260826-153000",
  "release_kind": "full",
  "upload_date": "2026-08-26",
  "uploaded_at": "2026-08-26T15:30:00-07:00",
  "blob_prefix": "2026-08-26/release-20260826-153000",
  "payload_contract_version": "1.2",
  "summary": {
    "products": 1,
    "payload_items": 2
  },
  "products": [
    {
      "product_key": "service-bus",
      "display_name": "Service Bus",
      "page_model": "pricing",
      "semantic_strategy": "simple_static",
      "items": [
        {
          "item_id": "service-bus/zh-cn",
          "language": "zh-cn",
          "blob_path": "2026-08-26/release-20260826-153000/payloads/zh-cn/pricing/service-bus.json"
        },
        {
          "item_id": "service-bus/en-us",
          "language": "en-us",
          "blob_path": "2026-08-26/release-20260826-153000/payloads/en-us/pricing/service-bus.json"
        }
      ]
    }
  ]
}
```

历史 Release 没有声明 `payload_contract_version` 时，delivery manifest 同样省略该字段。清单不写入连接串、账号密钥、本机源路径、审核人信息或内容摘要。

## 5. 敏感配置

本地开发把真实连接串放入项目根目录 `.env`：

```dotenv
AZURE_STORAGE_CONNECTION_STRING=<真实 Azure Storage 连接串>
AZURE_BLOB_CONTAINER_NAME=<预先创建的容器名称>
```

`.env` 被 Git 忽略；仓库只保留不含真实凭据的 `.env_example`。进程环境变量优先于 `.env`，便于部署环境使用安全的秘密注入方式。配置对象的文本表示和命令错误不会打印连接串。

## 6. 命令

先构建并核对 Release，再执行上传：

```bash
cp .env_example .env
# 在 .env 中填写真实连接串和容器

uv run python cli.py release-verify \
  --release-id <release-id>

uv run python cli.py release-upload \
  --release-id <release-id>
```

需要供自动化读取时可增加 `--json`。成功输出包含目标容器、上传日期、Release Blob 前缀、Payload 数量和 `delivery-manifest.json` 路径，但不包含连接串。
