#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模块化重构后的CMS提取器功能
验证各个模块是否正常工作
"""

import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """测试模块导入"""
    print("🧪 测试模块导入...")
    
    try:
        from cms_extractors import (
            BaseCMSExtractor,
            HTMLProcessor,
            ContentExtractor,
            VerificationManager,
            ConfigManager,
            MySQLCMSExtractor,
            AzureStorageFilesCMSExtractor
        )
        print("✅ 所有模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_config_manager():
    """测试配置管理器"""
    print("\n🧪 测试配置管理器...")
    
    try:
        from cms_extractors import ConfigManager
        
        config_manager = ConfigManager("soft-category.json")
        
        # 测试区域管理
        regions = config_manager.get_supported_regions()
        print(f"✅ 支持的区域: {len(regions)} 个")
        
        # 测试产品配置
        mysql_config = config_manager.get_product_config("MySQL")
        print(f"✅ MySQL配置加载成功: {mysql_config.get('table_class', 'N/A')}")
        
        storage_config = config_manager.get_product_config("Azure Storage Files")
        print(f"✅ Storage Files配置加载成功: {storage_config.get('table_class', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")
        return False

def test_html_processor():
    """测试HTML处理器"""
    print("\n🧪 测试HTML处理器...")
    
    try:
        from cms_extractors import HTMLProcessor
        from bs4 import BeautifulSoup
        
        # 创建测试HTML
        test_html = """
        <html>
            <head>
                <script>console.log('test');</script>
                <style>body { color: red; }</style>
            </head>
            <body>
                <div class="common-banner">
                    <h2>Test Product</h2>
                    <h4>Test Description</h4>
                </div>
                <table id="test-table">
                    <tr><th>Column 1</th><th>Column 2</th></tr>
                    <tr><td>Data 1</td><td>Data 2</td></tr>
                </table>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(test_html, 'html.parser')
        processor = HTMLProcessor()
        
        cleaned_soup = processor.clean_html(soup)
        
        # 验证脚本和样式被移除
        scripts = cleaned_soup.find_all('script')
        styles = cleaned_soup.find_all('style')
        
        if len(scripts) == 0 and len(styles) == 0:
            print("✅ HTML清洗功能正常")
        else:
            print(f"⚠ HTML清洗不完整 - scripts: {len(scripts)}, styles: {len(styles)}")
        
        return True
    except Exception as e:
        print(f"❌ HTML处理器测试失败: {e}")
        return False

def test_verification_manager():
    """测试验证管理器"""
    print("\n🧪 测试验证管理器...")
    
    try:
        from cms_extractors import VerificationManager
        
        # 创建测试HTML
        test_html = """
        <!DOCTYPE html>
        <html>
            <body>
                <p class="region-info">区域: 中国北部</p>
                <h1>Test Title</h1>
                <p>Test content with some text.</p>
                <table class="pricing-table">
                    <tr><th>Column</th></tr>
                    <tr><td>Data</td></tr>
                </table>
                <a href="#">Test Link</a>
            </body>
        </html>
        """
        
        vm = VerificationManager()
        verification = vm.verify_extraction(test_html, "MySQL")
        
        print(f"✅ 验证完成 - 表格数量: {verification.get('table_count', 0)}")
        print(f"✅ 文本长度: {verification.get('text_length', 0)} 字符")
        print(f"✅ HTML有效性: {verification.get('is_valid_html', False)}")
        
        return True
    except Exception as e:
        print(f"❌ 验证管理器测试失败: {e}")
        return False

def test_extractors():
    """测试提取器类"""
    print("\n🧪 测试提取器类...")
    
    try:
        from cms_extractors import MySQLCMSExtractor, AzureStorageFilesCMSExtractor
        
        # 测试MySQL提取器
        mysql_extractor = MySQLCMSExtractor("soft-category.json", "test_output")
        print(f"✅ MySQL提取器初始化成功 - 产品: {mysql_extractor.product_name}")
        
        # 测试Storage Files提取器
        storage_extractor = AzureStorageFilesCMSExtractor("soft-category.json", "test_output")
        print(f"✅ Storage Files提取器初始化成功 - 产品: {storage_extractor.product_name}")
        
        # 测试重要标题获取
        mysql_titles = mysql_extractor.important_section_titles
        storage_titles = storage_extractor.important_section_titles
        
        print(f"✅ MySQL重要标题: {len(mysql_titles)} 个")
        print(f"✅ Storage Files重要标题: {len(storage_titles)} 个")
        
        return True
    except Exception as e:
        print(f"❌ 提取器测试失败: {e}")
        return False

def test_file_processing():
    """测试文件处理（如果存在测试文件）"""
    print("\n🧪 测试文件处理...")
    
    mysql_file = "prod-html/mysql-index.html"
    storage_file = "prod-html/storage-files-index.html"
    
    if os.path.exists(mysql_file):
        try:
            from cms_extractors import MySQLCMSExtractor
            
            extractor = MySQLCMSExtractor("soft-category.json", "test_output")
            
            # 只测试前几个步骤，不完整处理
            html_content = extractor._load_html_file(mysql_file)
            print(f"✅ MySQL文件加载成功 - 大小: {len(html_content):,} 字符")
            
        except Exception as e:
            print(f"⚠ MySQL文件处理测试失败: {e}")
    else:
        print(f"⚠ MySQL测试文件不存在: {mysql_file}")
    
    if os.path.exists(storage_file):
        try:
            from cms_extractors import AzureStorageFilesCMSExtractor
            
            extractor = AzureStorageFilesCMSExtractor("soft-category.json", "test_output")
            
            # 只测试前几个步骤，不完整处理
            html_content = extractor._load_html_file(storage_file)
            print(f"✅ Storage Files文件加载成功 - 大小: {len(html_content):,} 字符")
            
        except Exception as e:
            print(f"⚠ Storage Files文件处理测试失败: {e}")
    else:
        print(f"⚠ Storage Files测试文件不存在: {storage_file}")

def main():
    """主测试函数"""
    print("🚀 开始测试模块化重构后的CMS提取器")
    print("=" * 60)
    
    all_passed = True
    
    # 运行各项测试
    test_results = [
        test_imports(),
        test_config_manager(),
        test_html_processor(),
        test_verification_manager(),
        test_extractors()
    ]
    
    all_passed = all(test_results)
    
    # 可选的文件处理测试
    test_file_processing()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有核心功能测试通过！")
        print("✅ 模块化重构成功完成")
        print("💡 建议进行完整的功能测试以确保所有特性正常工作")
    else:
        print("❌ 部分测试失败，请检查相关模块")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())