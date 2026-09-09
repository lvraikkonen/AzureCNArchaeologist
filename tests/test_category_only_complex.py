from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.core.catalog import CatalogError, ProductCatalog
from src.core.payload_contract import PayloadContractError, validate_pricing_payload
from src.extractors.strategy_extractor import _strategy_config
from src.machine_checks.independent_source import IndependentSourceError, locate_pricing_source
from src.machine_checks.l3b import run_l3b
from src.pipeline.coordinator import run_scope
from src.review.service import prepare_review_queue
from src.strategies.complex_content_strategy import ComplexContentStrategy

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=['zh-cn', 'en-us'])
def language(request):
    return request.param


@pytest.fixture
def project(project_builder):
    root = project_builder([{'product_key': 'databox', 'semantic_strategy': 'complex'}])
    config = root / 'data/configs/products-config/pricing/databox.json'
    shutil.copy2(ROOT / 'data/configs/products-config/pricing/databox.json', config)
    for language in ('zh-cn', 'en-us'):
        relative = Path(language) / 'pricing/details/databox/index.html'
        destination = root / 'data/current_prod_html' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'data/current_prod_html' / relative, destination)
    mapping = root / 'data/configs/soft-category.json'
    mapping.write_text('[]')
    return root


def source(project, language):
    return BeautifulSoup((project / 'data/current_prod_html' / language / 'pricing/details/databox/index.html').read_bytes(), 'html.parser')


def strategy(project, language, mode='category_only'):
    definition = ProductCatalog.load(project).get_definition('databox')
    config = _strategy_config(definition, language=language, project_root=project)
    config['extraction']['complex_mode'] = mode
    # The implementation is configuration driven, not conditional on this product key.
    config['product_key'] = 'another-tabbed-product'
    return ComplexContentStrategy(config)


def extract(project, language, soup=None):
    return strategy(project, language).extract_flexible_content(
        source(project, language) if soup is None else soup,
        f'https://www.azure.cn/{language}/pricing/details/databox/',
    )


def independent(project, language, soup, mode='category_only'):
    return locate_pricing_source(soup, product_key='another-tabbed-product', semantic_strategy='complex',
        language=language, soft_category_path=project / 'data/configs/soft-category.json', complex_mode=mode)


def validate(payload, language, mode='category_only'):
    validate_pricing_payload(payload, product_key='databox', language=language,
        semantic_strategy='complex', complex_mode=mode)


def test_category_only_retains_complete_tabs_without_region_lookups(project, language, monkeypatch):
    soup = source(project, language)
    original = str(soup)
    worker = strategy(project, language)
    def unexpected_lookup(*args):
        pytest.fail('Category-only must not query a region mapping')
    monkeypatch.setattr(type(worker.region_processor.rules), 'excluded_table_ids', unexpected_lookup)
    payload = worker.extract_flexible_content(soup, 'https://www.azure.cn/pricing/details/databox/')
    validate(payload, language)
    assert str(soup) == original
    definitions = json.loads(payload['pageConfig']['filtersJsonConfig'])['filterDefinitions']
    assert [row['filterKey'] for row in definitions] == ['category']
    assert [row['value'] for row in definitions[0]['options']] == ['tabContent1-4', 'tabContent1-1']
    assert [g['groupName'] for g in payload['contentGroups']] == ['Data Box', 'Data Box Disk']
    for group, target in zip(payload['contentGroups'], ['tabContent1-4', 'tabContent1-1']):
        assert json.loads(group['filterCriteriaJson']) == [{'filterKey': 'category', 'matchValues': target}]
        actual = BeautifulSoup(group['content'], 'html.parser')
        expected = soup.find(id=target)
        assert ' '.join(actual.get_text(' ', strip=True).split()) == ' '.join(expected.get_text(' ', strip=True).split())
        assert len(actual.find_all('table')) == len(expected.find_all('table'))
    expected = independent(project, language, soup)
    assert expected['filtersJsonConfig'] == payload['pageConfig']['filtersJsonConfig']
    assert [g['content'] for g in expected['contentGroups']] == [g['content'] for g in payload['contentGroups']]


def test_category_only_accepts_absent_region_control(project, language):
    soup = source(project, language)
    for node in soup.select('.region-container'):
        node.decompose()
    payload = extract(project, language, soup)
    validate(payload, language)
    assert len(independent(project, language, soup)['contentGroups']) == 2


@pytest.mark.parametrize('control', ['region-container', 'software-kind-container'])
def test_category_only_rejects_new_visible_dimensions(project, language, control):
    soup = source(project, language)
    soup.select_one('.' + control)['style'] = ''
    with pytest.raises(ValueError, match='category_only'):
        extract(project, language, soup)
    with pytest.raises(IndependentSourceError, match='category_only'):
        independent(project, language, soup)


def test_regular_complex_still_requires_visible_region(project, language):
    soup = source(project, language)
    with pytest.raises(ValueError, match='区域'):
        strategy(project, language, mode=None).extract_flexible_content(soup, "https://www.azure.cn/pricing/details/databox/")
    with pytest.raises(IndependentSourceError, match='区域'):
        independent(project, language, soup, mode=None)


def test_missing_category_target_blocks_both_walks(project, language):
    soup = source(project, language)
    soup.find(id='tabContent1-1').decompose()
    with pytest.raises(ValueError):
        extract(project, language, soup)
    with pytest.raises(IndependentSourceError):
        independent(project, language, soup)


@pytest.mark.parametrize('mutation', ['missing_group', 'missing_criterion', 'unexpected_region'])
def test_contract_rejects_incomplete_category_only_payload(project, language, mutation):
    payload = extract(project, language)
    if mutation == 'missing_group':
        payload['contentGroups'].pop()
    elif mutation == 'missing_criterion':
        payload['contentGroups'][0]['filterCriteriaJson'] = '[]'
    else:
        payload['contentGroups'][0]['filterCriteriaJson'] = json.dumps([{'filterKey': 'region', 'matchValues': 'east-china3'}])
    with pytest.raises(PayloadContractError):
        validate(payload, language)
    with pytest.raises(PayloadContractError):
        validate(extract(project, language), language, mode=None)


def test_l3b_detects_deleted_category_content(project, language, tmp_path):
    payload = extract(project, language)
    payload['contentGroups'][0]['content'] = '<p>missing prices</p>'
    path = tmp_path / 'payload.json'
    path.write_text(json.dumps(payload))
    report = run_l3b(frozen_html_path=project / 'data/current_prod_html' / language / 'pricing/details/databox/index.html',
        payload_path=path, product_key='databox', language=language, semantic_strategy='complex',
        soft_category_path=project / 'data/configs/soft-category.json', complex_mode='category_only')
    assert report['status'] == 'failed'


@pytest.mark.parametrize('mode,strategy_name', [('bad', 'complex'), ('category_only', 'simple_static')])
def test_catalog_rejects_invalid_mode(project, mode, strategy_name):
    path = project / 'data/configs/products-config/pricing/databox.json'
    config = json.loads(path.read_text())
    config['extraction'].update(complex_mode=mode, semantic_strategy=strategy_name)
    path.write_text(json.dumps(config))
    with pytest.raises(CatalogError, match='complex_mode'):
        ProductCatalog.load(project)


def test_batch_and_review_preserve_category_only_mode(project):
    catalog = ProductCatalog.load(project)
    result = run_scope(catalog, product_key='databox', run_name='category-only', runs_root=project / 'runs')
    assert result.succeeded
    assert all(row['complex_mode'] == 'category_only' for row in result.manifest['items'])
    queue = prepare_review_queue(catalog, run_name='category-only', review_id='category-review')
    assert queue is not None
    data = json.loads((project / 'reviews/category-review/queue.json').read_text())
    assert data['products'][0]['items'][0]['complex_mode'] == 'category_only'


def test_mode_changes_are_detected_and_review_uses_batch_mode(project):
    from src.incremental.product_definition_changes import build_product_definition_baseline, compare_product_definitions
    from src.review import ReviewError, ReviewWorkbenchService
    catalog = ProductCatalog.load(project)
    baseline = project / 'baseline.json'
    baseline.write_text(json.dumps(build_product_definition_baseline(catalog, source_run_name='before')))
    run_scope(catalog, product_key='databox', run_name='mode-review', runs_root=project / 'runs')
    prepare_review_queue(catalog, run_name='mode-review', review_id='mode-review')
    config_path = project / 'data/configs/products-config/pricing/databox.json'
    config = json.loads(config_path.read_text())
    config['extraction'].pop('complex_mode')
    config_path.write_text(json.dumps(config))
    current = ProductCatalog.load(project)
    changes = compare_product_definitions(current, baseline_path=baseline)
    assert changes[0].changed_fields == ('complex_mode',)
    workbench = ReviewWorkbenchService(current, review_id='mode-review')
    evidence = workbench.product_evidence('databox')
    assert all(row['summary']['matched'] == row['summary']['comparisons'] for row in evidence['languages'])
    path = project / 'reviews/mode-review/queue.json'
    queue = json.loads(path.read_text())
    queue['products'][0]['items'][0]['complex_mode'] = None
    path.write_text(json.dumps(queue))
    with pytest.raises(ReviewError, match='Complex 模式'):
        workbench.product_evidence('databox')
