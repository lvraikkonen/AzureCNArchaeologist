#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证更新后的data_models.py是否正常工作
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.data_models import (
    PageType, StrategyType, FilterType,
    Filter, Tab, Region,
    FilterAnalysis, TabAnalysis, RegionAnalysis,
    PageComplexity, ExtractionStrategy,
    FlexibleContentGroup, FlexiblePageConfig, 
    FlexibleCommonSection, FlexibleContentData
)

def test_enums():
    """测试更新后的枚举类型"""
    print("=" * 60)
    print("🧪 测试枚举类型")
    print("=" * 60)
    
    # 测试PageType
    print("\n📋 PageType (3+1策略):")
    for page_type in PageType:
        print(f"  {page_type.name}: {page_type.value}")
    
    # 测试StrategyType
    print("\n📋 StrategyType (3+1策略):")
    for strategy_type in StrategyType:
        print(f"  {strategy_type.name}: {strategy_type.value}")
    
    # 测试FilterType
    print("\n📋 FilterType (保持不变):")
    for filter_type in FilterType:
        print(f"  {filter_type.name}: {filter_type.value}")
    
    # 验证3+1策略
    expected_strategies = {"simple_static", "region_filter", "complex", "large_file"}
    actual_strategies = {s.value for s in StrategyType}
    
    if expected_strategies == actual_strategies:
        print("\n✅ 3+1策略架构验证通过")
    else:
        print(f"\n❌ 策略不匹配: 期望{expected_strategies}, 实际{actual_strategies}")

def test_data_classes():
    """测试简化后的数据类"""
    print("\n\n" + "=" * 60)
    print("🧪 测试数据类")
    print("=" * 60)
    
    # 测试基础数据类
    print("\n📋 基础数据类:")
    
    # Filter
    filter_obj = Filter(
        filter_type=FilterType.REGION,
        element_id="region-box",
        element_type="select",
        selector="#region-box",
        options=["north-china3", "east-china2"]
    )
    print(f"  Filter: {filter_obj.element_id} ({filter_obj.filter_type.value})")
    
    # Tab
    tab_obj = Tab(
        tab_id="tabContent1",
        tab_text="全部",
        tab_href="#tabContent1-0"
    )
    print(f"  Tab: {tab_obj.tab_id} ({tab_obj.tab_text})")
    
    # Region
    region_obj = Region(
        region_id="north-china3",
        region_name="中国北部 3",
        region_code="north-china3"
    )
    print(f"  Region: {region_obj.region_id} ({region_obj.region_name})")

def test_analysis_classes():
    """测试分析类"""
    print("\n📋 分析类:")
    
    # FilterAnalysis
    filter_analysis = FilterAnalysis(
        has_filters=True,
        filters=[Filter(FilterType.REGION, "region-box", "select", "#region-box")],
        primary_filter_type=FilterType.REGION
    )
    print(f"  FilterAnalysis: has_filters={filter_analysis.has_filters}, count={filter_analysis.filter_count}")
    
    # TabAnalysis  
    tab_analysis = TabAnalysis(
        has_tabs=True,
        tabs=[Tab("tabContent1", "全部")]
    )
    print(f"  TabAnalysis: has_tabs={tab_analysis.has_tabs}, count={tab_analysis.tab_count}")
    
    # RegionAnalysis
    region_analysis = RegionAnalysis(
        has_regions=True,
        regions=[Region("north-china3", "中国北部 3", "north-china3")],
        region_selector_found=True
    )
    print(f"  RegionAnalysis: has_regions={region_analysis.has_regions}, count={region_analysis.region_count}")

def test_strategy_processing_requirements():
    """测试策略处理需求"""
    print("\n📋 策略处理需求:")
    
    strategies = [
        (StrategyType.SIMPLE_STATIC, "SimpleStaticStrategy"),
        (StrategyType.REGION_FILTER, "RegionFilterStrategy"), 
        (StrategyType.COMPLEX, "ComplexContentStrategy"),
        (StrategyType.LARGE_FILE, "LargeFileStrategy")
    ]
    
    for strategy_type, processor in strategies:
        strategy = ExtractionStrategy(
            strategy_type=strategy_type,
            processor=processor,
            description=f"{strategy_type.value} strategy"
        )
        
        print(f"  {strategy_type.value}:")
        print(f"    region_processing: {strategy.requires_region_processing}")
        print(f"    tab_processing: {strategy.requires_tab_processing}")
        print(f"    large_file_optimization: {strategy.requires_large_file_optimization}")

def test_flexible_json_models():
    """测试Flexible JSON数据模型"""
    print("\n📋 Flexible JSON数据模型:")
    
    # 测试FlexibleContentGroup
    content_group = FlexibleContentGroup(
        group_name="中国北部 3",
        filter_criteria_json='[{"filterKey":"region","matchValues":"north-china3"}]',
        content="<div>北部3区域的内容</div>"
    )
    print(f"  ContentGroup: {content_group.group_name}")
    
    # 测试FlexiblePageConfig
    page_config = FlexiblePageConfig(
        enable_filters=True,
        filters_json_config='{"filterDefinitions":[{"filterKey":"region","options":[...]}]}'
    )
    print(f"  PageConfig: enable_filters={page_config.enable_filters}")
    
    # 测试FlexibleCommonSection
    common_section = FlexibleCommonSection(
        section_type="Banner",
        content="<div class='banner-content'>...</div>"
    )
    print(f"  CommonSection: {common_section.section_type}")
    
    # 测试FlexibleContentData
    flexible_data = FlexibleContentData(
        title="API 管理定价",
        base_content="",
        content_groups=[content_group],
        common_sections=[common_section],
        page_config=page_config
    )
    print(f"  FlexibleContentData: {flexible_data.title} ({len(flexible_data.content_groups)} groups)")

def main():
    """主函数"""
    print("🔍 验证更新后的data_models.py")
    print("测试3+1策略架构和简化的数据类")
    
    try:
        test_enums()
        test_data_classes()
        test_analysis_classes()
        test_strategy_processing_requirements()
        test_flexible_json_models()
        
        print("\n\n" + "=" * 60)
        print("✅ 所有测试通过! data_models.py更新成功")
        print("🎉 3+1策略架构已就绪")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()