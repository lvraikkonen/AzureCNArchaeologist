"""
Core data models for page analysis and extraction strategies.

This module defines the data structures used throughout the extraction pipeline:
- PageComplexity: Page structure analysis results
- ExtractionStrategy: Strategy selection information
- FilterAnalysis: Filter detection results
- TabAnalysis: Tab structure analysis results
- RegionAnalysis: Region detection results
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class PageType(Enum):
    """Supported page types for extraction strategies."""
    SIMPLE_STATIC = "simple_static"      # Type A: Simple static pages
    REGION_FILTER = "region_filter"      # Type B: Single region filter
    TAB = "tab"                         # Type C: Tab-based content
    REGION_TAB = "region_tab"           # Type D: Region + tab combination
    MULTI_FILTER = "multi_filter"       # Type E: Multiple filter types
    LARGE_FILE = "large_file"           # Special: Large files requiring optimization


class StrategyType(Enum):
    """Extraction strategy types."""
    SIMPLE_STATIC = "simple_static"
    REGION_FILTER = "region_filter"
    TAB = "tab"
    REGION_TAB = "region_tab"
    MULTI_FILTER = "multi_filter"
    LARGE_FILE = "large_file"


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
class FilterInfo:
    """Information about a detected filter."""
    filter_type: FilterType
    element_id: str
    selector_info: str
    options: List[str] = field(default_factory=list)
    default_value: Optional[str] = None
    is_region_related: bool = False


@dataclass
class TabInfo:
    """Information about a detected tab structure."""
    tab_id: str
    tab_text: str
    tab_selector: str
    is_region_related: bool = False
    is_default: bool = False


@dataclass
class RegionInfo:
    """Information about detected region selectors."""
    region_id: str
    region_name: str
    selector: str                       # CSS selector for region option
    is_available: bool = True          # Whether region is available


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
class RegionFilter(Filter):
    """Region-specific filter information."""
    def __post_init__(self):
        super().__post_init__() if hasattr(super(), '__post_init__') else None
        self.filter_type = FilterType.REGION


@dataclass
class Tab:
    """Tab information."""
    tab_id: str
    tab_text: str
    tab_href: str = ""
    target_content_id: str = ""
    is_active: bool = False
    element: Optional[Any] = None  # BeautifulSoup Tag
    navigation: Optional[Any] = None  # TabNavigation object


@dataclass
class TabNavigation:
    """Tab navigation structure."""
    nav_element: Any  # BeautifulSoup Tag
    tab_links: List[Any] = field(default_factory=list)  # BeautifulSoup Tags
    nav_type: str = "unknown"  # ul, div, etc.
    is_horizontal: bool = True


@dataclass
class TabContent:
    """Tab content area."""
    content_id: str
    content_element: Any  # BeautifulSoup Tag
    is_visible: bool = False
    associated_tab: Optional[str] = None  # tab_id


@dataclass
class RegionSelector:
    """Region selector information."""
    selector_element: Any  # BeautifulSoup Tag
    selector_type: str    # select, div, etc.
    region_options: List[str] = field(default_factory=list)
    default_region: Optional[str] = None
    is_functional: bool = True


@dataclass
class Region:
    """Region information."""
    region_id: str
    region_name: str
    region_code: str
    is_available: bool = True
    is_default: bool = False


# === Analysis classes (depend on base classes above) ===

@dataclass
class FilterAnalysis:
    """Results of filter detection analysis."""
    has_filters: bool
    filters: List[Filter] = field(default_factory=list)
    primary_filter_type: FilterType = FilterType.NONE
    filter_count: int = 0
    
    def __post_init__(self):
        self.filter_count = len(self.filters)


@dataclass
class TabAnalysis:
    """Results of tab structure analysis."""
    has_tabs: bool
    tabs: List[Tab] = field(default_factory=list)
    tab_count: int = 0
    navigations: List[TabNavigation] = field(default_factory=list)
    content_areas: List[TabContent] = field(default_factory=list)
    tab_types: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.tab_count = len(self.tabs)


@dataclass
class RegionAnalysis:
    """Results of region detection analysis."""
    has_regions: bool
    regions: List[Region] = field(default_factory=list)  
    region_selectors: List[RegionSelector] = field(default_factory=list)
    region_selector_found: bool = False
    active_regions: List[str] = field(default_factory=list)
    default_region: Optional[str] = None
    region_containers: List[Any] = field(default_factory=list)  # BeautifulSoup Tags
    region_count: int = 0
    
    def __post_init__(self):
        self.region_count = len(self.regions)


@dataclass
class PageComplexity:
    """Page complexity analysis results."""
    # Basic structure detection
    has_region_filter: bool
    has_tabs: bool
    has_multiple_filters: bool
    
    # Detailed analysis
    tab_count: int = 0
    filter_types: List[str] = field(default_factory=list)
    interactive_elements: int = 0
    estimated_complexity_score: float = 0.0
    
    # File characteristics
    file_size_mb: float = 0.0
    is_large_file: bool = False
    
    # Component analysis results
    filter_analysis: Optional[FilterAnalysis] = None
    tab_analysis: Optional[TabAnalysis] = None
    region_analysis: Optional[RegionAnalysis] = None
    
    def __post_init__(self):
        """Calculate derived values after initialization."""
        # Update filter types list
        if self.filter_analysis and self.filter_analysis.filters:
            self.filter_types = [f.filter_type.value for f in self.filter_analysis.filters]
        
        # Update tab count
        if self.tab_analysis:
            self.tab_count = self.tab_analysis.tab_count
        
        # Calculate complexity score
        self._calculate_complexity_score()
    
    def _calculate_complexity_score(self) -> None:
        """Calculate overall complexity score (0.0 to 10.0)."""
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
        
        # File size impact
        if self.is_large_file:
            score += 3.0
        elif self.file_size_mb > 1.0:
            score += 1.0
        
        self.estimated_complexity_score = min(score, 10.0)


@dataclass
class ExtractionStrategy:
    """Extraction strategy selection information."""
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
    requires_large_file_optimization: bool = False
    
    def __post_init__(self):
        """Set processing requirements based on strategy type."""
        if self.strategy_type in [StrategyType.REGION_FILTER, StrategyType.REGION_TAB, StrategyType.MULTI_FILTER]:
            self.requires_region_processing = True
        
        if self.strategy_type in [StrategyType.TAB, StrategyType.REGION_TAB, StrategyType.MULTI_FILTER]:
            self.requires_tab_processing = True
            
        if self.strategy_type == StrategyType.LARGE_FILE:
            self.requires_large_file_optimization = True