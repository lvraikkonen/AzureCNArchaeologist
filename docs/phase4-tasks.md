# Phase 4: RAG导出器增强 - 详细任务清单

## 🎯 **Phase 4 目标**

重点开发RAG知识库创建功能，实现智能文档分块、语义增强和向量嵌入优化，为知识库建设提供高质量的数据准备。

**预计时间**: 4-5天  
**核心交付物**: RAG专用工具包 + 增强的RAG导出器 + 向量嵌入支持  
**验证标准**: RAG导出质量显著提升，支持多种知识库格式

---

## 📋 **任务清单**

### **4.1 RAG数据模型设计** (0.5天)

#### 4.1.1 核心数据结构定义
- [ ] 创建`src/core/rag_models.py`:
  ```python
  from dataclasses import dataclass
  from typing import List, Dict, Any, Optional
  
  @dataclass
  class DocumentChunk:
      chunk_id: str
      content: str
      chunk_type: str  # "banner", "description", "pricing", "faq", "feature"
      metadata: Dict[str, Any]
      source_section: str
      word_count: int
      estimated_tokens: int
  
  @dataclass
  class PricingChunk(DocumentChunk):
      service_tier: str
      pricing_details: Dict[str, Any]
      region_specific: bool
      currency: str
  
  @dataclass
  class QAChunk(DocumentChunk):
      question: str
      answer: str
      confidence_score: float
      related_topics: List[str]
  
  @dataclass
  class ProductContext:
      product_name: str
      product_category: str
      related_services: List[str]
      key_features: List[str]
      pricing_model: str
      supported_regions: List[str]
  
  @dataclass
  class VectorDocument:
      document_id: str
      chunks: List[DocumentChunk]
      product_context: ProductContext
      embedding_metadata: Dict[str, Any]
      created_at: str
  ```

**验证标准**: 数据模型设计合理，支持各种RAG应用场景

#### 4.1.2 RAG配置模型
- [ ] 定义RAG导出配置:
  ```python
  @dataclass
  class RAGExportConfig:
      max_chunk_size: int = 1000
      overlap_size: int = 100
      chunk_strategy: str = "semantic"  # "semantic", "fixed", "adaptive"
      include_metadata: bool = True
      preserve_structure: bool = True
      embedding_model: str = "text-embedding-ada-002"
      vector_db_format: str = "pinecone"  # "pinecone", "weaviate", "chroma"
  ```

**验证标准**: 配置模型支持不同的RAG场景和向量数据库

### **4.2 智能文档分块器** (1.5天)

#### 4.2.1 语义分块器
- [ ] 创建`src/utils/rag/document_splitter.py`:
  ```python
  class DocumentSplitter:
      """智能文档分块器 - 语义感知"""
      
      def __init__(self, config: RAGExportConfig):
          self.config = config
          self.text_analyzer = TextAnalyzer()
      
      def split_by_semantic_sections(self, content: str, 
                                   content_type: str) -> List[DocumentChunk]:
          """按语义区域分块，保持内容完整性"""
          
          # 1. 识别内容结构
          sections = self._identify_content_sections(content, content_type)
          
          # 2. 语义边界检测
          chunks = []
          for section in sections:
              section_chunks = self._split_section_semantically(section)
              chunks.extend(section_chunks)
          
          # 3. 优化分块大小
          optimized_chunks = self._optimize_chunk_sizes(chunks)
          
          return optimized_chunks
      
      def split_pricing_tables(self, tables: List[Dict]) -> List[PricingChunk]:
          """专门处理定价表格的分块逻辑"""
          pricing_chunks = []
          
          for table in tables:
              # 按服务层级分块
              tier_chunks = self._split_by_service_tiers(table)
              
              # 按区域分块
              region_chunks = self._split_by_regions(table)
              
              # 合并和优化
              merged_chunks = self._merge_pricing_chunks(tier_chunks, region_chunks)
              pricing_chunks.extend(merged_chunks)
          
          return pricing_chunks
      
      def create_qa_chunks(self, qa_content: str) -> List[QAChunk]:
          """将FAQ内容转换为QA知识块"""
          qa_pairs = self._extract_qa_pairs(qa_content)
          
          qa_chunks = []
          for pair in qa_pairs:
              chunk = QAChunk(
                  chunk_id=self._generate_chunk_id("qa", pair["question"]),
                  content=f"Q: {pair['question']}\nA: {pair['answer']}",
                  chunk_type="faq",
                  question=pair["question"],
                  answer=pair["answer"],
                  confidence_score=self._calculate_qa_confidence(pair),
                  related_topics=self._extract_related_topics(pair),
                  metadata={"source": "faq_section"},
                  source_section="faq",
                  word_count=len(pair["answer"].split()),
                  estimated_tokens=self._estimate_tokens(pair["answer"])
              )
              qa_chunks.append(chunk)
          
          return qa_chunks
      
      def _identify_content_sections(self, content: str, 
                                   content_type: str) -> List[ContentSection]:
          """识别内容的语义结构"""
          soup = BeautifulSoup(content, 'html.parser')
          
          sections = []
          
          if content_type == "banner":
              sections = self._analyze_banner_structure(soup)
          elif content_type == "description":
              sections = self._analyze_description_structure(soup)
          elif content_type == "pricing":
              sections = self._analyze_pricing_structure(soup)
          
          return sections
      
      def _split_section_semantically(self, section: ContentSection) -> List[DocumentChunk]:
          """在语义边界处分割内容"""
          # 使用自然语言处理识别段落边界
          paragraphs = self._extract_paragraphs(section.content)
          
          chunks = []
          current_chunk = ""
          current_metadata = section.metadata.copy()
          
          for paragraph in paragraphs:
              # 检查添加段落后是否超过大小限制
              potential_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
              
              if self._estimate_tokens(potential_chunk) <= self.config.max_chunk_size:
                  current_chunk = potential_chunk
              else:
                  # 保存当前块
                  if current_chunk:
                      chunks.append(self._create_document_chunk(
                          current_chunk, section.chunk_type, current_metadata
                      ))
                  
                  # 开始新块
                  current_chunk = paragraph
          
          # 添加最后一个块
          if current_chunk:
              chunks.append(self._create_document_chunk(
                  current_chunk, section.chunk_type, current_metadata
              ))
          
          return chunks
  ```

**验证标准**: 
- 能正确识别不同内容类型的语义结构
- 分块大小合理，保持语义完整性
- 支持不同的分块策略

#### 4.2.2 自适应分块器
- [ ] 实现自适应分块逻辑:
  ```python
  def split_adaptively(self, content: str, content_type: str) -> List[DocumentChunk]:
      """根据内容特征自适应分块"""
      
      # 分析内容特征
      content_features = self._analyze_content_features(content)
      
      # 选择最佳分块策略
      if content_features.has_complex_structure:
          return self.split_by_semantic_sections(content, content_type)
      elif content_features.is_list_heavy:
          return self._split_by_list_items(content, content_type)
      elif content_features.is_table_heavy:
          return self._split_by_table_sections(content, content_type)
      else:
          return self._split_by_fixed_size(content, content_type)
  ```

**验证标准**: 自适应逻辑能根据内容特征选择最佳分块方式

### **4.3 知识点提取器** (1天)

#### 4.3.1 产品特性提取
- [ ] 创建`src/utils/rag/knowledge_extractor.py`:
  ```python
  class KnowledgeExtractor:
      """知识点提取器"""
      
      def __init__(self):
          self.feature_patterns = self._load_feature_patterns()
          self.pricing_patterns = self._load_pricing_patterns()
      
      def extract_product_features(self, content: str) -> List[Feature]:
          """提取产品特性知识点"""
          soup = BeautifulSoup(content, 'html.parser')
          
          features = []
          
          # 从列表中提取特性
          features.extend(self._extract_from_lists(soup))
          
          # 从段落中提取特性
          features.extend(self._extract_from_paragraphs(soup))
          
          # 从表格中提取特性
          features.extend(self._extract_from_tables(soup))
          
          # 去重和分类
          unique_features = self._deduplicate_features(features)
          categorized_features = self._categorize_features(unique_features)
          
          return categorized_features
      
      def extract_pricing_rules(self, pricing_data: Dict) -> List[PricingRule]:
          """提取定价规则知识"""
          pricing_rules = []
          
          # 提取层级定价规则
          tier_rules = self._extract_tier_rules(pricing_data)
          pricing_rules.extend(tier_rules)
          
          # 提取区域定价规则
          region_rules = self._extract_region_rules(pricing_data)
          pricing_rules.extend(region_rules)
          
          # 提取计费规则
          billing_rules = self._extract_billing_rules(pricing_data)
          pricing_rules.extend(billing_rules)
          
          return pricing_rules
      
      def extract_service_capabilities(self, description: str) -> List[Capability]:
          """提取服务能力描述"""
          capabilities = []
          
          # 使用NLP模式匹配
          capability_matches = self._find_capability_patterns(description)
          
          for match in capability_matches:
              capability = Capability(
                  name=match.capability_name,
                  description=match.description,
                  category=match.category,
                  confidence_score=match.confidence,
                  related_features=match.related_features
              )
              capabilities.append(capability)
          
          return capabilities
      
      def _extract_from_lists(self, soup: BeautifulSoup) -> List[Feature]:
          """从HTML列表中提取特性"""
          features = []
          
          for ul in soup.find_all(['ul', 'ol']):
              # 检查是否为特性列表
              if self._is_feature_list(ul):
                  for li in ul.find_all('li'):
                      feature_text = li.get_text(strip=True)
                      if self._is_valid_feature(feature_text):
                          feature = Feature(
                              name=self._extract_feature_name(feature_text),
                              description=feature_text,
                              category=self._classify_feature(feature_text),
                              confidence_score=self._calculate_feature_confidence(feature_text)
                          )
                          features.append(feature)
          
          return features
  ```

**验证标准**: 
- 能准确提取产品特性
- 定价规则提取准确
- 服务能力识别正确

#### 4.3.2 语义关系提取
- [ ] 实现语义关系分析:
  ```python
  def extract_semantic_relationships(self, chunks: List[DocumentChunk]) -> Dict[str, List[str]]:
      """提取文档块之间的语义关系"""
      
      relationships = {}
      
      for i, chunk in enumerate(chunks):
          related_chunks = []
          
          for j, other_chunk in enumerate(chunks):
              if i != j:
                  similarity = self._calculate_semantic_similarity(chunk, other_chunk)
                  if similarity > 0.7:  # 相似度阈值
                      related_chunks.append(other_chunk.chunk_id)
          
          relationships[chunk.chunk_id] = related_chunks
      
      return relationships
  ```

**验证标准**: 语义关系提取准确，相关度计算合理

### **4.4 上下文构建器** (1天)

#### 4.4.1 产品上下文构建
- [ ] 创建`src/utils/rag/context_builder.py`:
  ```python
  class ContextBuilder:
      """上下文构建器"""
      
      def build_product_context(self, product_data: Dict) -> ProductContext:
          """构建产品完整上下文"""
          
          # 提取产品基本信息
          basic_info = self._extract_basic_info(product_data)
          
          # 分析产品特性
          features = self._analyze_product_features(product_data)
          
          # 确定定价模型
          pricing_model = self._determine_pricing_model(product_data)
          
          # 识别支持的区域
          supported_regions = self._identify_supported_regions(product_data)
          
          return ProductContext(
              product_name=basic_info.name,
              product_category=basic_info.category,
              related_services=self._find_related_services(basic_info.name),
              key_features=features,
              pricing_model=pricing_model,
              supported_regions=supported_regions
          )
      
      def link_related_services(self, current_product: str, 
                              all_products: List[str]) -> List[Relation]:
          """构建产品间关联关系"""
          relations = []
          
          # 基于产品名称相似性
          name_relations = self._find_name_based_relations(current_product, all_products)
          relations.extend(name_relations)
          
          # 基于功能相似性
          feature_relations = self._find_feature_based_relations(current_product, all_products)
          relations.extend(feature_relations)
          
          # 基于使用场景相似性
          scenario_relations = self._find_scenario_based_relations(current_product, all_products)
          relations.extend(scenario_relations)
          
          return self._deduplicate_relations(relations)
      
      def enrich_with_metadata(self, chunks: List[DocumentChunk]) -> List[EnrichedChunk]:
          """为文档块添加丰富的元数据"""
          enriched_chunks = []
          
          for chunk in chunks:
              # 添加语义标签
              semantic_tags = self._generate_semantic_tags(chunk)
              
              # 添加主题分类
              topics = self._classify_topics(chunk)
              
              # 添加实体识别
              entities = self._extract_entities(chunk)
              
              # 添加情感分析（如果适用）
              sentiment = self._analyze_sentiment(chunk)
              
              enriched_chunk = EnrichedChunk(
                  **chunk.__dict__,
                  semantic_tags=semantic_tags,
                  topics=topics,
                  entities=entities,
                  sentiment=sentiment,
                  enrichment_timestamp=datetime.now().isoformat()
              )
              
              enriched_chunks.append(enriched_chunk)
          
          return enriched_chunks
  ```

**验证标准**: 
- 产品上下文信息完整准确
- 服务关联关系合理
- 元数据丰富度高

#### 4.4.2 跨产品知识图谱
- [ ] 实现知识图谱构建:
  ```python
  def build_knowledge_graph(self, all_products_data: Dict[str, Dict]) -> KnowledgeGraph:
      """构建跨产品知识图谱"""
      
      graph = KnowledgeGraph()
      
      # 添加产品节点
      for product_name, product_data in all_products_data.items():
          product_node = self._create_product_node(product_name, product_data)
          graph.add_node(product_node)
      
      # 添加关系边
      for product_name in all_products_data.keys():
          relations = self.link_related_services(product_name, list(all_products_data.keys()))
          
          for relation in relations:
              edge = self._create_relation_edge(product_name, relation)
              graph.add_edge(edge)
      
      # 添加概念节点（如"数据库"、"AI服务"等）
      concept_nodes = self._extract_concept_nodes(all_products_data)
      for node in concept_nodes:
          graph.add_node(node)
      
      return graph
  ```

**验证标准**: 知识图谱结构合理，关系准确

### **4.5 增强RAG导出器** (1天)

#### 4.5.1 向量数据库格式支持
- [ ] 重构`src/exporters/rag_exporter.py`:
  ```python
  class RAGExporter:
      """RAG格式导出器 - 知识库优化版"""
      
      def __init__(self, output_dir: str, config: RAGExportConfig):
          self.output_dir = Path(output_dir)
          self.config = config
          self.document_splitter = DocumentSplitter(config)
          self.knowledge_extractor = KnowledgeExtractor()
          self.context_builder = ContextBuilder()
      
      def export_for_vector_db(self, data: Dict, product_name: str) -> List[VectorDocument]:
          """导出为向量数据库格式"""
          
          # 1. 构建产品上下文
          product_context = self.context_builder.build_product_context(data)
          
          # 2. 智能分块
          all_chunks = []
          
          # Banner内容分块
          if data.get("BannerContent"):
              banner_chunks = self.document_splitter.split_by_semantic_sections(
                  data["BannerContent"], "banner"
              )
              all_chunks.extend(banner_chunks)
          
          # 描述内容分块
          if data.get("DescriptionContent"):
              desc_chunks = self.document_splitter.split_by_semantic_sections(
                  data["DescriptionContent"], "description"
              )
              all_chunks.extend(desc_chunks)
          
          # 定价表格分块
          if data.get("PricingTables"):
              pricing_chunks = self.document_splitter.split_pricing_tables(
                  data["PricingTables"]
              )
              all_chunks.extend(pricing_chunks)
          
          # FAQ内容分块
          if data.get("QaContent"):
              qa_chunks = self.document_splitter.create_qa_chunks(data["QaContent"])
              all_chunks.extend(qa_chunks)
          
          # 3. 上下文丰富
          enriched_chunks = self.context_builder.enrich_with_metadata(all_chunks)
          
          # 4. 创建向量文档
          vector_doc = VectorDocument(
              document_id=f"{product_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
              chunks=enriched_chunks,
              product_context=product_context,
              embedding_metadata={
                  "model": self.config.embedding_model,
                  "chunk_strategy": self.config.chunk_strategy,
                  "total_chunks": len(enriched_chunks)
              },
              created_at=datetime.now().isoformat()
          )
          
          return [vector_doc]
      
      def export_for_pinecone(self, vector_docs: List[VectorDocument]) -> str:
          """导出为Pinecone格式"""
          pinecone_data = []
          
          for doc in vector_docs:
              for chunk in doc.chunks:
                  pinecone_record = {
                      "id": chunk.chunk_id,
                      "values": [],  # 嵌入向量将在客户端生成
                      "metadata": {
                          "product_name": doc.product_context.product_name,
                          "chunk_type": chunk.chunk_type,
                          "content": chunk.content,
                          "source_section": chunk.source_section,
                          "word_count": chunk.word_count,
                          "estimated_tokens": chunk.estimated_tokens,
                          **chunk.metadata
                      }
                  }
                  pinecone_data.append(pinecone_record)
          
          # 输出为JSON Lines格式
          output_file = self.output_dir / f"pinecone_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
          
          with open(output_file, 'w', encoding='utf-8') as f:
              for record in pinecone_data:
                  f.write(json.dumps(record, ensure_ascii=False) + '\n')
          
          return str(output_file)
      
      def export_for_chroma(self, vector_docs: List[VectorDocument]) -> str:
          """导出为Chroma格式"""
          chroma_data = {
              "documents": [],
              "metadatas": [],
              "ids": []
          }
          
          for doc in vector_docs:
              for chunk in doc.chunks:
                  chroma_data["documents"].append(chunk.content)
                  chroma_data["metadatas"].append({
                      "product_name": doc.product_context.product_name,
                      "chunk_type": chunk.chunk_type,
                      "source_section": chunk.source_section,
                      **chunk.metadata
                  })
                  chroma_data["ids"].append(chunk.chunk_id)
          
          output_file = self.output_dir / f"chroma_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
          
          with open(output_file, 'w', encoding='utf-8') as f:
              json.dump(chroma_data, f, ensure_ascii=False, indent=2)
          
          return str(output_file)
      
      def export_semantic_chunks(self, data: Dict, product_name: str) -> List[SemanticChunk]:
          """导出语义优化的文档块"""
          
          # 使用高级分块策略
          chunks = self.document_splitter.split_adaptively(
              data.get("DescriptionContent", ""), "description"
          )
          
          # 语义增强
          semantic_chunks = []
          for chunk in chunks:
              # 提取关键概念
              key_concepts = self.knowledge_extractor.extract_key_concepts(chunk.content)
              
              # 生成摘要
              summary = self._generate_chunk_summary(chunk.content)
              
              # 识别意图
              intent = self._classify_chunk_intent(chunk.content)
              
              semantic_chunk = SemanticChunk(
                  **chunk.__dict__,
                  key_concepts=key_concepts,
                  summary=summary,
                  intent=intent,
                  semantic_score=self._calculate_semantic_score(chunk.content)
              )
              
              semantic_chunks.append(semantic_chunk)
          
          return semantic_chunks
  ```

**验证标准**: 
- 支持多种向量数据库格式
- 导出数据质量高
- 分块和语义增强效果好

#### 4.5.2 嵌入优化支持
- [ ] 添加嵌入优化功能:
  ```python
  def optimize_for_embeddings(self, chunks: List[DocumentChunk]) -> List[OptimizedChunk]:
      """为嵌入模型优化文档块"""
      
      optimized_chunks = []
      
      for chunk in chunks:
          # 清理文本（移除HTML标签、多余空白等）
          cleaned_content = self._clean_text_for_embedding(chunk.content)
          
          # 添加上下文信息
          contextual_content = self._add_context_to_chunk(cleaned_content, chunk)
          
          # 优化长度
          if len(contextual_content.split()) > self.config.max_chunk_size:
              contextual_content = self._truncate_intelligently(contextual_content)
          
          optimized_chunk = OptimizedChunk(
              **chunk.__dict__,
              optimized_content=contextual_content,
              optimization_metadata={
                  "original_length": len(chunk.content),
                  "optimized_length": len(contextual_content),
                  "optimization_applied": True
              }
          )
          
          optimized_chunks.append(optimized_chunk)
      
      return optimized_chunks
  ```

**验证标准**: 优化后的内容更适合嵌入模型处理

### **4.6 集成和测试** (1天)

#### 4.6.1 完整流程测试
- [ ] 测试API Management的RAG导出:
  ```bash
  python cli.py extract api-management --html-file data/prod-html/api-management-index.html --format rag --output-dir test_rag_output
  ```

- [ ] 验证RAG导出质量:
  - 分块数量合理（预期10-20个块）
  - 每个块内容语义完整
  - 元数据丰富准确
  - 向量数据库格式正确

**验证标准**: RAG导出功能完全正常，质量显著提升

#### 4.6.2 多格式导出测试
- [ ] 测试Pinecone格式导出
- [ ] 测试Chroma格式导出
- [ ] 测试语义块导出
- [ ] 测试向量优化功能

**验证标准**: 各种格式导出正确，适配不同的向量数据库

#### 4.6.3 性能和质量测试
- [ ] 测试分块质量:
  - 语义完整性评分>0.8
  - 块大小分布合理
  - 重叠处理正确

- [ ] 测试知识提取质量:
  - 特性提取准确率>85%
  - 定价规则识别正确
  - 关系构建合理

**验证标准**: 质量指标达到预期，性能可接受

---

## 🎯 **成功标准**

### 功能标准
- ✅ RAG导出功能显著增强
- ✅ 支持智能文档分块
- ✅ 支持多种向量数据库格式
- ✅ 知识提取准确率>85%
- ✅ 语义增强效果明显

### 技术标准
- ✅ 分块算法智能化
- ✅ 上下文信息丰富
- ✅ 向量嵌入优化
- ✅ 可扩展的格式支持

### 质量标准
- ✅ 语义完整性>0.8
- ✅ 知识覆盖度>90%
- ✅ 导出数据准确性>95%

---

## 🚧 **风险和缓解措施**

### 高风险项
1. **分块质量不佳**
   - 风险：语义分块破坏内容完整性
   - 缓解：多种分块策略，质量评估机制

2. **知识提取不准确**
   - 风险：特性和规则提取错误
   - 缓解：模式库优化，人工验证机制

### 中风险项
1. **性能问题**
   - 风险：复杂的NLP处理导致速度慢
   - 缓解：缓存机制，并行处理

2. **格式兼容性**
   - 风险：导出格式不兼容目标系统
   - 缓解：充分测试，标准化格式

---

## 📝 **每日检查点**

### Day 1 结束
- [ ] RAG数据模型设计完成
- [ ] DocumentSplitter基础框架完成

### Day 2 结束
- [ ] 智能分块器完全实现
- [ ] 分块质量测试通过

### Day 3 结束
- [ ] KnowledgeExtractor实现完成
- [ ] 知识提取准确率达标

### Day 4 结束
- [ ] ContextBuilder实现完成
- [ ] RAGExporter重构完成

### Day 5 结束
- [ ] 所有格式导出测试通过
- [ ] 性能和质量达标
- [ ] 文档更新完成

---

## 🎉 **项目完成里程碑**

Phase 4完成后，整个重构项目达成：

### 架构目标 ✅
- ✅ 模块化、可扩展的架构
- ✅ 策略化的页面处理
- ✅ 高质量的RAG数据输出

### 功能目标 ✅  
- ✅ 支持5种页面类型处理
- ✅ 支持多种导出格式
- ✅ 智能化的内容分析

### 质量目标 ✅
- ✅ 代码质量显著提升
- ✅ 功能完全向后兼容
- ✅ 性能保持或提升

**🚀 项目重构成功完成！**