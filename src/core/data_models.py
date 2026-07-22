"""
Core data models for the semantic extraction strategies.

This module defines the data structures used throughout the extraction pipeline:
- PageType & StrategyType: three pricing strategies plus Support Article
- PageComplexity: Page structure analysis results
- ExtractionStrategy: Strategy selection information  
- FilterAnalysis: Filter detection results
- TabAnalysis: Tab structure analysis results
- RegionAnalysis: Region detection results
- FlexibleContentData: Flexible JSON content models

Supports the semantic strategy architecture:
- SimpleStatic: Simple static pages (event-grid, service-bus)
- RegionFilter: Region filter pages (api-management, hdinsight)  
- Complex: Complex pages (cloud-services)
- SupportArticle: SLA/ICP/legal/public-security articles
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class PageType(Enum):
    """Supported semantic page types."""
    SIMPLE_STATIC = "simple_static"      # Type A: Simple static pages (event-grid, service-bus)
    REGION_FILTER = "region_filter"      # Type B: Region filter pages (api-management, hdinsight)
    COMPLEX = "complex"                  # Type C: Complex pages (cloud-services)
    SUPPORT_ARTICLE = "support_article"  # Support article pages (SLA/ICP/Legal/公安备案)


class StrategyType(Enum):
    """Extraction strategy types; processing mode is deliberately orthogonal."""
    SIMPLE_STATIC = "simple_static"
    REGION_FILTER = "region_filter"
    COMPLEX = "complex"                  # Replaces: TAB, REGION_TAB, MULTI_FILTER
    SUPPORT_ARTICLE = "support_article"


class FilterType(Enum):
    """Types of filters found on pricing pages."""
    NONE = "none"
    REGION = "region"
    OS = "operating_system"
    TIER = "service_tier"
    STORAGE = "storage_type"
    COMPUTE = "compute_size"
    OTHER = "other"


# === Base classes (dependencies first) ===


@dataclass
class Filter:
    """Base filter information."""
    filter_type: FilterType
    element_id: str
    element_type: str
    selector: str
    options: List[str] = field(default_factory=list)
    is_active: bool = True
    default_value: Optional[str] = None




@dataclass
class Tab:
    """Simplified tab information for 3+1 strategy architecture."""
    tab_id: str
    tab_text: str
    tab_href: str = ""
    target_content_id: str = ""
    is_active: bool = False


@dataclass
class Region:
    """Simplified region information for 3+1 strategy architecture."""
    region_id: str
    region_name: str
    region_code: str
    is_available: bool = True


# === Analysis classes (depend on base classes above) ===

@dataclass
class FilterAnalysis:
    """Results of filter detection analysis for 3+1 strategy architecture."""
    has_filters: bool
    filters: List[Filter] = field(default_factory=list)
    primary_filter_type: FilterType = FilterType.NONE
    
    @property
    def filter_count(self) -> int:
        """Calculate filter count dynamically."""
        return len(self.filters)


@dataclass
class TabAnalysis:
    """Results of tab structure analysis for 3+1 strategy architecture."""
    has_tabs: bool
    tabs: List[Tab] = field(default_factory=list)
    
    @property 
    def tab_count(self) -> int:
        """Calculate tab count dynamically."""
        return len(self.tabs)


@dataclass
class RegionAnalysis:
    """Results of region detection analysis for 3+1 strategy architecture."""
    has_regions: bool
    regions: List[Region] = field(default_factory=list)
    region_selector_found: bool = False
    default_region: Optional[str] = None
    
    @property
    def region_count(self) -> int:
        """Calculate region count dynamically."""
        return len(self.regions)


@dataclass
class PageComplexity:
    """Semantic page-structure analysis results."""
    # Basic structure detection (for backward compatibility)
    has_region_filter: bool
    has_tabs: bool
    has_multiple_filters: bool
    
    interactive_elements: int = 0
    
    # Component analysis results
    filter_analysis: Optional[FilterAnalysis] = None
    tab_analysis: Optional[TabAnalysis] = None
    region_analysis: Optional[RegionAnalysis] = None
    
    @property
    def tab_count(self) -> int:
        """Get tab count from analysis."""
        return self.tab_analysis.tab_count if self.tab_analysis else 0
    
    @property
    def filter_types(self) -> List[str]:
        """Get filter types from analysis."""
        if self.filter_analysis and self.filter_analysis.filters:
            return [f.filter_type.value for f in self.filter_analysis.filters]
        return []
    
    @property
    def estimated_complexity_score(self) -> float:
        """Calculate complexity score (0.0 to 10.0) for 3+1 strategy architecture."""
        score = 0.0
        
        # Base complexity
        if self.has_region_filter:
            score += 2.0
        if self.has_tabs:
            score += 1.5 * self.tab_count
        if self.has_multiple_filters:
            score += 1.0 * len(self.filter_types)
        
        # Interactive elements
        score += min(self.interactive_elements * 0.1, 2.0)
        
        return min(score, 10.0)


@dataclass
class ExtractionStrategy:
    """Semantic extraction strategy selection information."""
    strategy_type: StrategyType
    processor: str                              # Processor class name
    description: str = ""                       # Human-readable description
    features: List[str] = field(default_factory=list)  # Supported features
    priority_features: List[str] = field(default_factory=list)  # High-priority features
    config_overrides: Dict[str, Any] = field(default_factory=dict)  # Config overrides
    complexity_score: float = 0.0               # Page complexity score
    recommended_page_type: PageType = PageType.SIMPLE_STATIC  # Recommended page type
    
    # Processing requirements (set in __post_init__)
    requires_region_processing: bool = False
    requires_tab_processing: bool = False
    
    def __post_init__(self):
        """Set processing requirements based on 3+1 strategy type."""
        # Region processing for REGION_FILTER and COMPLEX strategies
        if self.strategy_type in [StrategyType.REGION_FILTER, StrategyType.COMPLEX]:
            self.requires_region_processing = True
        
        # Tab processing for COMPLEX strategy (includes old TAB, REGION_TAB, MULTI_FILTER)
        if self.strategy_type == StrategyType.COMPLEX:
            self.requires_tab_processing = True
            
        expected_page_type = PageType(self.strategy_type.value)
        if self.recommended_page_type != expected_page_type:
            raise ValueError(
                "recommended_page_type must match the semantic strategy type: "
                f"{self.strategy_type.value}"
            )


# === Flexible JSON Content Models ===

@dataclass
class FlexibleContentGroup:
    """Content group for Flexible JSON format."""
    group_name: str
    filter_criteria_json: str
    content: str


@dataclass
class FlexiblePageConfig:
    """Page configuration for Flexible JSON format."""
    enable_filters: bool = False
    filters_json_config: str = ""


@dataclass
class FlexibleCommonSection:
    """Common section for Flexible JSON format."""
    section_type: str  # "Banner", "ProductDescription", "Qa", etc.
    content: str


@dataclass
class FlexibleContentData:
    """Complete Flexible JSON content structure."""
    title: str
    base_content: str = ""
    content_groups: List[FlexibleContentGroup] = field(default_factory=list)
    common_sections: List[FlexibleCommonSection] = field(default_factory=list)
    page_config: Optional[FlexiblePageConfig] = None
