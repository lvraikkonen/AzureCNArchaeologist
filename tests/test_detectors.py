#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证FilterDetector和TabDetector的功能
基于文档中的预期测试结果进行验证
"""

import sys
import os
from pathlib import Path
from bs4 import BeautifulSoup

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.detectors.filter_detector import FilterDetector
from src.detectors.tab_detector import TabDetector

def load_html_file(file_path: str) -> BeautifulSoup:
    """加载HTML文件并返回BeautifulSoup对象"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return BeautifulSoup(content, 'html.parser')
    except Exception as e:
        print(f"❌ 加载文件失败 {file_path}: {e}")
        return None

def test_filter_detector():
    """测试FilterDetector功能"""
    print("=" * 60)
    print("🧪 测试 FilterDetector")
    print("=" * 60)
    
    detector = FilterDetector()
    
    # 测试用例定义（基于文档预期结果）
    test_cases = [
        {
            "file": "data/prod-html/compute/cloud-services.html",
            "description": "cloud-services.html: 应检测到隐藏software + 可见region",
            "expected": {
                "has_software": True,
                "software_visible": False,
                "has_region": True, 
                "region_visible": True
            }
        },
        {
            "file": "data/prod-html/compute/app-service.html",
            "description": "app-service.html: 可见software + 可见region",
            "expected": {
                "has_software": True,
                "software_visible": True,
                "has_region": True, 
                "region_visible": True
            }
        },
        {
            "file": "data/prod-html/compute/azure-functions.html",
            "description": "azure-functions.html: 应检测到隐藏software + 可见region",
            "expected": {
                "has_software": True,
                "software_visible": False,
                "has_region": True, 
                "region_visible": True
            }
        },
        {
            "file": "data/prod-html/compute/virtual-machine-scale-sets.html",
            "description": "virtual-machine-scale-sets.html: 可见software + 可见region",
            "expected": {
                "has_software": True,
                "software_visible": True,
                "has_region": True, 
                "region_visible": True
            }
        },
        {
            "file": "data/prod-html/analysis/analysis-services.html", 
            "description": "analysis-services.html: 应检测到隐藏software + 可见region",
            "expected": {
                "has_software": True,
                "software_visible": False,
                "has_region": True,
                "region_visible": True
            }
        },
        {
            "file": "data/prod-html/analysis/hdinsight.html", 
            "description": "hdinsight.html: 应检测到隐藏software + 可见region",
            "expected": {
                "has_software": True,
                "software_visible": False,
                "has_region": True,
                "region_visible": True
            }
        },
        {
            "file": "data/prod-html/analysis/stream-analytics.html",
            "description": "stream-analytics.html: 应检测到无筛选器", 
            "expected": {
                "has_software": False,
                "software_visible": False,
                "has_region": False,
                "region_visible": False
            }
        },
        {
            "file": "data/prod-html/integration/api-management.html", 
            "description": "api-management.html: 应检测到隐藏software + 可见region",
            "expected": {
                "has_software": True,
                "software_visible": False,
                "has_region": True,
                "region_visible": True
            }
        },
        {
            "file": "data/prod-html/integration/event-grid.html",
            "description": "event-grid.html: 应检测到无筛选器", 
            "expected": {
                "has_software": False,
                "software_visible": False,
                "has_region": False,
                "region_visible": False
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试 {i}: {test_case['description']}")
        
        # 检查文件是否存在
        if not os.path.exists(test_case['file']):
            print(f"⚠ 文件不存在: {test_case['file']}")
            continue
            
        # 加载HTML
        soup = load_html_file(test_case['file'])
        if not soup:
            continue
            
        # 执行检测
        try:
            result = detector.detect_filters(soup)
            
            # 验证结果
            expected = test_case['expected']
            passed = True
            
            for key, expected_value in expected.items():
                actual_value = result.get(key)
                if actual_value != expected_value:
                    print(f"❌ {key}: 期望={expected_value}, 实际={actual_value}")
                    passed = False
                else:
                    print(f"✅ {key}: {actual_value}")
            
            if passed:
                print(f"🎉 测试 {i} 通过!")
                
                # 显示额外信息
                if result.get('software_options'):
                    print(f"   软件选项数量: {len(result['software_options'])}")
                if result.get('region_options'):
                    print(f"   地区选项数量: {len(result['region_options'])}")
            else:
                print(f"❌ 测试 {i} 失败!")
                
        except Exception as e:
            print(f"❌ 测试执行出错: {e}")

def test_tab_detector():
    """测试TabDetector功能"""
    print("\n\n" + "=" * 60)
    print("🧪 测试 TabDetector")
    print("=" * 60)
    
    detector = TabDetector()
    
    # 测试用例定义
    test_cases = [
        {
            "file": "data/prod-html/compute/cloud-services.html",
            "description": "cloud-services.html: container=True, groups=1, total_category_tabs=4",
            "expected": {
                "has_main_container": True,
                "has_tabs": True,
                "content_groups_count": 1,
                "total_category_tabs": 4,
                "has_complex_tabs": True
            }
        },
        {
            "file": "data/prod-html/compute/app-service.html",
            "description": "app-service.html: container=True, groups=2, total_category_tabs=0",
            "expected": {
                "has_main_container": True,
                "has_tabs": False,
                "content_groups_count": 2,
                "total_category_tabs": 0,
                "has_complex_tabs": False
            }
        },
        {
            "file": "data/prod-html/compute/azure-functions.html",
            "description": "azure-functions.html: container=True, groups=1, total_category_tabs=0",
            "expected": {
                "has_main_container": True,
                "has_tabs": False,
                "content_groups_count": 1,
                "total_category_tabs": 0,
                "has_complex_tabs": False
            }
        },
        {
            "file": "data/prod-html/compute/virtual-machine-scale-sets.html",
            "description": "virtual-machine-scale-sets.html: container=True, groups=7, total_category_tabs=33",
            "expected": {
                "has_main_container": True,
                "has_tabs": True,
                "content_groups_count": 7,
                "total_category_tabs": 33,
                "has_complex_tabs": True
            }
        },
        {
            "file": "data/prod-html/analysis/hdinsight.html",
            "description": "hdinsight.html: container=True, groups=1, total_category_tabs=0", 
            "expected": {
                "has_main_container": True,
                "has_tabs": False,
                "content_groups_count": 1,
                "total_category_tabs": 0,
                "has_complex_tabs": False
            }
        },
        {
            "file": "data/prod-html/integration/api-management.html",
            "description": "api-management.html: container=True, groups=1, total_category_tabs=0", 
            "expected": {
                "has_main_container": True,
                "has_tabs": False,
                "content_groups_count": 1,
                "total_category_tabs": 0,
                "has_complex_tabs": False
            }
        },
        {
            "file": "data/prod-html/integration/event-grid.html",
            "description": "event-grid.html: container=False, groups=0, total_category_tabs=0",
            "expected": {
                "has_main_container": False,
                "has_tabs": False,
                "content_groups_count": 0,
                "total_category_tabs": 0,
                "has_complex_tabs": False
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试 {i}: {test_case['description']}")
        
        # 检查文件是否存在
        if not os.path.exists(test_case['file']):
            print(f"⚠ 文件不存在: {test_case['file']}")
            continue
            
        # 加载HTML
        soup = load_html_file(test_case['file'])
        if not soup:
            continue
            
        # 执行检测
        try:
            result = detector.detect_tabs(soup)
            
            # 验证结果
            expected = test_case['expected']
            passed = True
            
            # 检查容器和基本tab
            for key in ['has_main_container', 'has_tabs', 'has_complex_tabs']:
                actual_value = result.get(key)
                expected_value = expected.get(key)
                if actual_value != expected_value:
                    print(f"❌ {key}: 期望={expected_value}, 实际={actual_value}")
                    passed = False
                else:
                    print(f"✅ {key}: {actual_value}")
            
            # 检查content_groups数量 (新的输出格式)
            actual_groups = len(result.get('content_groups', []))
            expected_groups = expected.get('content_groups_count')
            if actual_groups != expected_groups:
                print(f"❌ content_groups_count: 期望={expected_groups}, 实际={actual_groups}")
                passed = False
            else:
                print(f"✅ content_groups_count: {actual_groups}")
                
            # 检查total_category_tabs (新的输出格式)
            actual_total = result.get('total_category_tabs', 0)
            expected_total = expected.get('total_category_tabs')
            if actual_total != expected_total:
                print(f"❌ total_category_tabs: 期望={expected_total}, 实际={actual_total}")
                passed = False
            else:
                print(f"✅ total_category_tabs: {actual_total}")
            
            if passed:
                print(f"🎉 测试 {i} 通过!")
                
                # 显示详细信息
                if result.get('content_groups'):
                    group_ids = [group.get('id') for group in result['content_groups']]
                    print(f"   分组容器: {group_ids}")
                if result.get('category_tabs'):
                    categories = [f"{tab.get('label')}({tab.get('group_id')})" for tab in result['category_tabs']]
                    print(f"   真实Tab (前5个): {categories[:5]}")
            else:
                print(f"❌ 测试 {i} 失败!")
                
        except Exception as e:
            print(f"❌ 测试执行出错: {e}")

def main():
    """主函数"""
    print("🔍 开始验证昨天实现的检测器功能")
    print("基于 docs/flexible-content-implementation.md 中的预期结果")
    
    # 测试FilterDetector
    test_filter_detector()
    
    # 测试TabDetector
    test_tab_detector()
    
    print("\n\n" + "=" * 60)
    print("✅ 验证完成")
    print("=" * 60)

if __name__ == "__main__":
    main()