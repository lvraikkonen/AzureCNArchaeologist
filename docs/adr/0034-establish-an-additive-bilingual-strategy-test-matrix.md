# Establish an Additive Bilingual Strategy Test Matrix

Status: Accepted

The v0.4 Core Strategy Test Matrix runs both `zh-cn` and `en-us` for `service-bus` (`simple_static`), `api-management` (`region_filter`), `cloud-services` (`complex`), and `icp-faq` (`support_article`) across unit, component, and end-to-end coverage. Each of the three pricing representatives carries both a complete Golden Payload for canonical Business Payload regression and a Curated Pricing Fact Baseline for independent validator calibration, while `icp-faq` carries article-content and CMS-contract baselines. As additional products complete calibration and review they are promoted additively within their strategy; the core representatives cannot be silently replaced or removed, because a rotating sample set would erase stable longitudinal regression evidence.
