# ADR 0001: Product Definitions and a Derived Catalog

Status: Accepted

Product identity, catalog grouping, and source routing previously depended on category-owned files and path inference, which allowed duplicate products and configuration drift. We will keep exactly one Product Definition per globally unique Product Key, model pricing catalog membership as a many-to-many `catalog_categories` list, classify support content with an independent `support_article_type`, and declare every language-specific Source Location explicitly. `products-index.json` is a deterministic, digest-bearing projection of those definitions. Category-owned duplicate definitions, manually maintained indexes, and source-path guessing were rejected because they create multiple editable facts for the same page. This makes configuration migration intentionally breaking, while allowing catalog views and normalized paths to evolve without changing product identity.
