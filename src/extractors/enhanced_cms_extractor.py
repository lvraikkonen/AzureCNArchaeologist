"""Thin public client for the explicit v0.2 extraction interface."""

from pathlib import Path

from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.extraction_result import ExtractionResult


class EnhancedCMSExtractor:
    def __init__(self, output_dir: str = "output", config_file: str = "") -> None:
        self.output_dir = Path(output_dir)
        self.coordinator = ExtractionCoordinator(str(self.output_dir))

    def extract_cms_content(
        self,
        product_key: str,
        language: str,
        html_file_path: str | None = None,
        version_key: str | None = None,
    ) -> ExtractionResult:
        return self.coordinator.coordinate_extraction(product_key, language, html_file_path, version_key)

    def extract_flexible_content(
        self,
        product_key: str,
        language: str,
        html_file_path: str | None = None,
        version_key: str | None = None,
    ) -> ExtractionResult:
        return self.extract_cms_content(product_key, language, html_file_path, version_key)
