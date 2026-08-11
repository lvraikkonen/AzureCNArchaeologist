from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from bs4 import BeautifulSoup

from scripts import qualify_v04_in_memory_capability as qualification
from src.core.data_models import StrategyType


def _qualification_worker_harness(
    tmp_path,
) -> tuple[
    Path,
    mock.Mock,
    mock.Mock,
    mock.Mock,
    mock.Mock,
    object,
]:
    raw = b"<!doctype html><html><body><table><tr><td>1</td></tr></table></body></html>"
    source_path = tmp_path / "qualification.html"
    source_path.write_bytes(raw)
    definition = {
        "sources": {
            qualification.LANGUAGE: {
                "url": "https://example.invalid/qualification",
            }
        }
    }
    strategy = SimpleNamespace(strategy_type=StrategyType.COMPLEX)
    manager = mock.Mock()
    manager.get_product_config.return_value = definition
    strategy_manager = mock.Mock()
    strategy_manager.determine_extraction_strategy.return_value = strategy
    strategy_instance = mock.Mock()
    strategy_instance.extract_flexible_content.return_value = {"title": "test"}
    resolver = mock.Mock()
    structural_reachability = object()
    strict_reachability = object()
    resolver.resolve.return_value = structural_reachability
    resolver.attach_strict_soft_category_projections.return_value = (
        strict_reachability
    )
    return (
        source_path,
        manager,
        strategy_manager,
        strategy_instance,
        resolver,
        strict_reachability,
    )


def test_complex_qualification_attaches_strict_projection_with_same_resolver(
    tmp_path,
    capsys,
):
    (
        source_path,
        manager,
        strategy_manager,
        strategy_instance,
        resolver,
        strict_reachability,
    ) = _qualification_worker_harness(tmp_path)

    with (
        mock.patch.object(
            qualification.ReconstructionParseabilityValidator,
            "validate",
            return_value=SimpleNamespace(
                passed=True,
                production_soup=BeautifulSoup(
                    source_path.read_text(encoding="utf-8"),
                    "html.parser",
                ),
                evidence={"fingerprints": {"document": "test"}},
            ),
        ),
        mock.patch.object(
            qualification,
            "ProductManager",
            return_value=manager,
        ),
        mock.patch.object(
            qualification,
            "StrategyManager",
            return_value=strategy_manager,
        ),
        mock.patch.object(
            qualification.StrategyFactory,
            "create_strategy",
            return_value=strategy_instance,
        ),
        mock.patch.object(
            qualification,
            "preprocess_image_paths",
            side_effect=lambda soup: soup,
        ),
        mock.patch.object(
            qualification,
            "SourceReachabilityResolver",
            return_value=resolver,
        ) as resolver_class,
        mock.patch.object(
            qualification.ExtractionCoordinator,
            "_normalize_business_fields",
        ),
    ):
        assert qualification._worker(source_path) == 0

    capsys.readouterr()
    resolver_class.assert_called_once_with(qualification.ROOT)
    assert [item[0] for item in resolver.mock_calls] == [
        "resolve",
        "attach_strict_soft_category_projections",
    ]
    canonical_input = resolver.resolve.call_args.args[0]
    resolver.attach_strict_soft_category_projections.assert_called_once_with(
        canonical_input,
        resolver.resolve.return_value,
    )
    strategy_instance.extract_flexible_content.assert_called_once_with(
        mock.ANY,
        "https://example.invalid/qualification",
        source_reachability=strict_reachability,
    )


def test_complex_qualification_fails_before_extract_when_projection_fails(
    tmp_path,
):
    (
        source_path,
        manager,
        strategy_manager,
        strategy_instance,
        resolver,
        _strict_reachability,
    ) = _qualification_worker_harness(tmp_path)
    resolver.attach_strict_soft_category_projections.side_effect = RuntimeError(
        "strict projection failed"
    )

    with (
        mock.patch.object(
            qualification.ReconstructionParseabilityValidator,
            "validate",
            return_value=SimpleNamespace(
                passed=True,
                production_soup=BeautifulSoup(
                    source_path.read_text(encoding="utf-8"),
                    "html.parser",
                ),
                evidence={"fingerprints": {"document": "test"}},
            ),
        ),
        mock.patch.object(
            qualification,
            "ProductManager",
            return_value=manager,
        ),
        mock.patch.object(
            qualification,
            "StrategyManager",
            return_value=strategy_manager,
        ),
        mock.patch.object(
            qualification.StrategyFactory,
            "create_strategy",
            return_value=strategy_instance,
        ),
        mock.patch.object(
            qualification,
            "preprocess_image_paths",
            side_effect=lambda soup: soup,
        ),
        mock.patch.object(
            qualification,
            "SourceReachabilityResolver",
            return_value=resolver,
        ),
        mock.patch.object(
            qualification.ExtractionCoordinator,
            "_normalize_business_fields",
        ),
    ):
        with pytest.raises(RuntimeError, match="strict projection failed"):
            qualification._worker(source_path)

    strategy_instance.extract_flexible_content.assert_not_called()
