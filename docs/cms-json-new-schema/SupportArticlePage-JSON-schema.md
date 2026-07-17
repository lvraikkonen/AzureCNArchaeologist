#### 支持类文章SupportArticlePage

##### 模型变更

模型从`SlaContentPage`变更为`SupportArticlePage`，新的模型将支持SLA，ICP备案，法律和公安备案四个类型。

##### 导入接口

`/api/Importer/ImportSupportArticlePageFromJson`此接口为导入支持类文章的**示例接口**，其实现是从种子数据中读取并导入过程的演示。

##### JSON示例

```json
{
  "title": "认知服务的服务级别协议",
  "slug": "cognitive-services",
  "metaTitle": "认知服务的服务级别协议 | Azure",
  "metaDescription": "认知服务的服务级别协议",
  "metaKeywords": "",
  "pageType": "sla",
  "lastModifiedDate":"2025年07月",
  "articleDescription":"<p>我们保证，认知服务将在不少于 99.9% 的时间内可用。没有为免费层级提供任何服务级别协议。</p>",
  "mainContent":"<h2>引言</h2><p>本 Azure 服务级别协议（以下简称“服务级别协议”）由世纪互联制定，与客户从世纪互联处购买 Azure 服务所依据的协议（以下简称“协议”）相关并构成该协议的一部分。</p><p>为了保证达到并保持所提供服务的服务级别，我们会提供财务方面的支持。如果我们未能达到和保持本服务级别协议中说明的每种服务的服务级别，则您有资格获得月度服务费用的部分服务费抵扣。在您的协议期间，这些条款都不会做任何变动。如果续展订购，则在续订期限开始时实行的本服务级别协议的版本将适用于整个续订期限。如果对本服务级别协议有任何重大不利变更，我们应至少提前九十 (90) 天进行通知。您可以随时访问 <a id=\"cognitive-services-sla_sla\" href=\"../../legal/sla/index.html\" aria-label=\"cognitive-services-sla_sla\">https://www.azure.cn/support/legal/sla/</a>查看本服务级别协议的最新版本。</p>"
}
```

**其中pageType必须为sla,Legal,Icp, psb其中一种，忽略大小写。**
