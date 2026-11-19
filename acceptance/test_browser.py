"""Tests in a browser, for the parts implemented in JavaScript."""
import pytest
from playwright.sync_api import sync_playwright

from helpers import PRODUCTION_NODES, PUPPETBOARD_URL, XSS_FACT


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


class Page:
    """A browser page, collecting the JavaScript errors."""

    def __init__(self, browser):
        self.page = browser.new_page()
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))

    def goto(self, path):
        self.page.goto(PUPPETBOARD_URL + path, wait_until='networkidle')
        return self.page


@pytest.fixture
def page(browser):
    page = Page(browser)
    yield page
    page.page.close()


def visible_rows(page, table):
    rows = f'{table} tbody tr:visible:not(:has(td.dataTables_empty))'
    return page.locator(rows).count()


def wait_for_rows(page, table):
    page.wait_for_selector(f'{table} tbody tr td:not(.dataTables_empty)')


@pytest.mark.parametrize('path', [
    '/', '/nodes', '/node/node-changed.example.com', '/failures', '/facts',
    '/fact/kernelrelease', '/reports', '/inventory', '/catalogs',
    '/catalog/node-changed.example.com', '/classes', '/query', '/radiator',
])
def test_page_loads(page, path):
    page.goto(path)
    assert page.errors == []


@pytest.mark.parametrize('path, table', [
    ('/reports', '#reports_table'),
    ('/inventory', '#inventory_table'),
    ('/catalogs', '#catalogs_table'),
    ('/fact/kernelrelease', '#facts_table'),
])
def test_ajax_tables(page, path, table):
    browser_page = page.goto(path)
    wait_for_rows(browser_page, table)
    assert visible_rows(browser_page, table) == len(PRODUCTION_NODES)
    assert page.errors == []


@pytest.mark.parametrize('search, expected', [
    ('node-changed', 1),
    ('node-(changed|failed)', 2),
    # not a valid regex, searched as plain text
    ('node-(', 0),
])
def test_nodes_filter(page, search, expected):
    browser_page = page.goto('/nodes')
    browser_page.fill('#main-table-search', search)
    assert visible_rows(browser_page, '#main-table') == expected
    assert page.errors == []


@pytest.mark.parametrize('path, table', [
    ('/node/node-changed.example.com', '#facts_table'),
    ('/fact/banner', '#facts_table'),
])
def test_fact_value_is_escaped(page, path, table):
    browser_page = page.goto(path)
    wait_for_rows(browser_page, table)

    assert browser_page.locator(table, has_text=XSS_FACT).count() == 1
    assert browser_page.evaluate('window.xss') is None
    assert page.errors == []
