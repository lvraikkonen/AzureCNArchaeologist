#!/usr/bin/env python3
"""
Azure CN Archaeologist - HTML文件自动复制脚本

根据products-index.json配置文件，自动从current_prod_html中查找对应的HTML文件，
复制到相应分组文件夹并重命名为产品名.html

支持多语言版本：zh-cn 和 en-us
目标结构：data/prod-html/{language}/{category}/{product}.html

作者: Azure CN Archaeologist
日期: 2025-09-04
"""

import os
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# 使用项目的日志系统
from src.core.logging import get_logger

logger = get_logger(__name__)

class HTMLFileCopier:
    """HTML文件自动复制器"""

    def __init__(self, base_dir: str = "."):
        """
        初始化复制器

        Args:
            base_dir: 项目根目录
        """
        self.base_dir = Path(base_dir)
        self.config_file = self.base_dir / "data" / "configs" / "products-index.json"
        self.current_html_dir = self.base_dir / "data" / "current_prod_html"
        self.target_html_dir = self.base_dir / "data" / "prod-html"

        # 特殊映射规则
        self.special_mappings = {
            # 产品名称 -> (文件夹路径, 文件名)
            "storage-files": ("storage/files", "index.html"),
            "data-lake-storage": ("storage/data-lake", "index.html"),
            "anomaly-detector": ("cognitive-services/anomaly-detector", "index.html"),
            "metrics-advisor": ("cognitive-services/metrics-advisor", "index.html"),
            "ssis": ("data-factory", "ssis.html"),
            "core-control-plane": ("azure-arc/core-control-plane", "index.html"),
        }

        # 产品名称别名映射（处理配置中的名称与实际文件夹名称不同的情况）
        self.product_name_mappings = {
            # 配置中的名称 -> 实际文件夹名称
        }

        # 分组映射（处理配置文件中的分组名称与目标文件夹名称不一致的情况）
        self.category_mappings = {
            # "ai-ml": "ai"
            # "dev-tool": "dev-tools"
        }

    def load_config(self) -> Dict:
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"成功加载配置文件: {self.config_file}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise

    def find_html_file(self, product_name: str, language: str = "zh-cn") -> Optional[Path]:
        """
        查找产品对应的HTML文件

        Args:
            product_name: 产品名称
            language: 语言版本 (zh-cn 或 en-us)

        Returns:
            找到的HTML文件路径，如果未找到返回None
        """
        # 检查特殊映射
        if product_name in self.special_mappings:
            folder_path, file_name = self.special_mappings[product_name]
            html_file = self.current_html_dir / language / "pricing" / "details" / folder_path / file_name
            if html_file.exists():
                logger.info(f"找到特殊映射文件: {product_name} -> {html_file}")
                return html_file

        # 检查产品名称映射
        actual_product_name = self.product_name_mappings.get(product_name, product_name)

        # 标准查找路径
        standard_path = self.current_html_dir / language / "pricing" / "details" / actual_product_name / "index.html"
        if standard_path.exists():
            logger.info(f"找到标准路径文件: {product_name} -> {standard_path}")
            return standard_path

        # 尝试查找其他可能的文件名
        product_dir = self.current_html_dir / language / "pricing" / "details" / actual_product_name
        if product_dir.exists() and product_dir.is_dir():
            # 查找所有HTML文件
            html_files = list(product_dir.glob("*.html"))
            if html_files:
                # 优先选择index.html，否则选择第一个
                for html_file in html_files:
                    if html_file.name == "index.html":
                        logger.info(f"找到index.html文件: {product_name} -> {html_file}")
                        return html_file

                # 如果没有index.html，选择第一个HTML文件
                logger.info(f"找到HTML文件: {product_name} -> {html_files[0]}")
                return html_files[0]

        logger.warning(f"未找到产品HTML文件: {product_name} (实际查找: {actual_product_name}, 语言: {language})")
        return None

    def copy_html_file(self, source_file: Path, target_category: str, product_name: str, language: str) -> bool:
        """
        复制HTML文件到目标位置

        Args:
            source_file: 源文件路径
            target_category: 目标分组
            product_name: 产品名称
            language: 语言版本

        Returns:
            复制是否成功
        """
        try:
            # 处理分组映射
            actual_category = self.category_mappings.get(target_category, target_category)

            # 创建目标目录 - 支持多语言结构
            target_dir = self.target_html_dir / language / actual_category
            target_dir.mkdir(parents=True, exist_ok=True)

            # 目标文件路径
            target_file = target_dir / f"{product_name}.html"

            # 复制文件
            shutil.copy2(source_file, target_file)
            logger.info(f"成功复制文件: {source_file} -> {target_file}")
            return True

        except Exception as e:
            logger.error(f"复制文件失败: {source_file} -> {language}/{target_category}/{product_name}.html, 错误: {e}")
            return False

    def process_category(self, category_name: str, category_config: Dict, language: str = "zh-cn") -> Tuple[int, int]:
        """
        处理单个分组的所有产品

        Args:
            category_name: 分组名称
            category_config: 分组配置
            language: 语言版本

        Returns:
            (成功数量, 失败数量)
        """
        products = category_config.get("products", [])
        success_count = 0
        fail_count = 0

        logger.info(f"开始处理分组: {category_name} (产品数量: {len(products)}, 语言: {language})")

        for product_name in products:
            logger.info(f"处理产品: {product_name}")

            # 查找HTML文件
            html_file = self.find_html_file(product_name, language)
            if html_file is None:
                logger.error(f"跳过产品 {product_name}: 未找到HTML文件")
                fail_count += 1
                continue

            # 复制文件
            if self.copy_html_file(html_file, category_name, product_name, language):
                success_count += 1
            else:
                fail_count += 1

        logger.info(f"分组 {category_name} 处理完成: 成功 {success_count}, 失败 {fail_count}")
        return success_count, fail_count

    def run(self, language: str = "zh-cn", categories: Optional[List[str]] = None) -> Dict:
        """
        运行自动复制流程

        Args:
            language: 语言版本 (zh-cn 或 en-us)
            categories: 要处理的分组列表，None表示处理所有分组

        Returns:
            处理结果统计
        """
        logger.info(f"开始HTML文件自动复制流程 (语言: {language})")

        # 加载配置
        config = self.load_config()
        all_categories = config.get("categories", {})

        # 确定要处理的分组
        if categories is None:
            target_categories = all_categories
        else:
            target_categories = {k: v for k, v in all_categories.items() if k in categories}

        # 统计信息
        total_success = 0
        total_fail = 0
        category_results = {}

        # 处理每个分组
        for category_name, category_config in target_categories.items():
            success, fail = self.process_category(category_name, category_config, language)
            total_success += success
            total_fail += fail
            category_results[category_name] = {"success": success, "fail": fail}

        # 输出总结
        logger.info("=" * 60)
        logger.info("处理结果总结:")
        logger.info(f"语言版本: {language}")
        logger.info(f"处理分组数: {len(target_categories)}")
        logger.info(f"成功复制: {total_success} 个文件")
        logger.info(f"失败: {total_fail} 个文件")
        logger.info("=" * 60)

        return {
            "language": language,
            "total_success": total_success,
            "total_fail": total_fail,
            "categories": category_results
        }

    def run_both_languages(self, categories: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        运行两种语言版本的复制流程

        Args:
            categories: 要处理的分组列表，None表示处理所有分组

        Returns:
            两种语言的处理结果统计
        """
        results = {}

        # 处理中文版本
        logger.info("开始处理中文版本 (zh-cn)")
        results["zh-cn"] = self.run("zh-cn", categories)

        # 处理英文版本
        logger.info("开始处理英文版本 (en-us)")
        results["en-us"] = self.run("en-us", categories)

        # 输出总体统计
        total_zh_success = results["zh-cn"]["total_success"]
        total_zh_fail = results["zh-cn"]["total_fail"]
        total_en_success = results["en-us"]["total_success"]
        total_en_fail = results["en-us"]["total_fail"]

        logger.info("=" * 80)
        logger.info("总体处理结果:")
        logger.info(f"中文版本: 成功 {total_zh_success}, 失败 {total_zh_fail}")
        logger.info(f"英文版本: 成功 {total_en_success}, 失败 {total_en_fail}")
        logger.info(f"总计: 成功 {total_zh_success + total_en_success}, 失败 {total_zh_fail + total_en_fail}")
        logger.info("=" * 80)

        return results


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Azure CN Archaeologist HTML文件自动复制工具")
    parser.add_argument("--language", "-l", choices=["zh-cn", "en-us", "both"], default="both",
                       help="语言版本 (默认: both - 处理两种语言)")
    parser.add_argument("--categories", "-c", nargs="+",
                       help="要处理的分组列表 (默认: 处理所有分组)")
    parser.add_argument("--base-dir", "-d", default=".",
                       help="项目根目录 (默认: 当前目录)")

    args = parser.parse_args()

    # 创建复制器
    copier = HTMLFileCopier(args.base_dir)

    # 根据参数运行
    if args.language == "both":
        results = copier.run_both_languages(args.categories)

        # 输出结果
        print(f"\n处理完成!")
        print(f"中文版本: 成功 {results['zh-cn']['total_success']}, 失败 {results['zh-cn']['total_fail']}")
        print(f"英文版本: 成功 {results['en-us']['total_success']}, 失败 {results['en-us']['total_fail']}")

        total_success = results['zh-cn']['total_success'] + results['en-us']['total_success']
        total_fail = results['zh-cn']['total_fail'] + results['en-us']['total_fail']
        print(f"总计: 成功 {total_success}, 失败 {total_fail}")

        # 显示失败的分组
        if total_fail > 0:
            print("\n失败的分组:")
            for lang, lang_results in results.items():
                for category, stats in lang_results['categories'].items():
                    if stats['fail'] > 0:
                        print(f"  {lang}/{category}: {stats['fail']} 个失败")
    else:
        result = copier.run(args.language, args.categories)

        # 输出结果
        print(f"\n处理完成!")
        print(f"语言: {args.language}")
        print(f"成功: {result['total_success']} 个文件")
        print(f"失败: {result['total_fail']} 个文件")

        if result['total_fail'] > 0:
            print("\n失败的分组:")
            for category, stats in result['categories'].items():
                if stats['fail'] > 0:
                    print(f"  {category}: {stats['fail']} 个失败")


if __name__ == "__main__":
    main()