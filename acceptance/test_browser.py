"""Tests in a browser, for the parts implemented in JavaScript."""
import pytest
from playwright.sync_api import sync_playwright

from helpers import (PRODUCTION_NODES, PUPPETBOARD_URL, XSS, XSS_NODE,
                     link_href)


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

    assert browser_page.locator(table, has_text=XSS).count() == 1
    assert browser_page.evaluate('window.xss') is None
    assert page.errors == []


def assert_not_executed(page, browser_page):
    assert browser_page.evaluate('window.xss') is None
    assert page.errors == []


@pytest.mark.parametrize('path, table', [
    ('/xss/reports', '#reports_table'),
    ('/xss/inventory', '#inventory_table'),
    ('/xss/fact/kernelrelease', '#facts_table'),
    (f'/xss/node/{XSS_NODE}', '#facts_table'),
])
def test_agent_data_is_escaped_in_tables(page, path, table):
    browser_page = page.goto(path)
    wait_for_rows(browser_page, table)

    assert browser_page.locator(table, has_text=XSS).count() == 1
    assert_not_executed(page, browser_page)


@pytest.mark.parametrize('path', [
    '/xss/failures',
    '/xss/facts',
    f'/xss/catalog/{XSS_NODE}',
])
def test_agent_data_is_escaped_in_pages(page, path):
    browser_page = page.goto(path)

    assert XSS in browser_page.inner_text('body')
    assert_not_executed(page, browser_page)


@pytest.mark.parametrize('show_error_as', ['', '/raw'])
def test_agent_data_is_escaped_in_report(page, puppetboard, show_error_as):
    row = puppetboard.get_json(f'/xss/reports/{XSS_NODE}/json',
                               params={'draw': 1, 'start': 0,
                                       'length': 10})['data'][0]
    browser_page = page.goto(link_href(row[1]) + show_error_as)
    wait_for_rows(browser_page, '#logs_table')

    assert XSS in browser_page.inner_text('body')
    assert browser_page.locator('#logs_table', has_text=XSS).count() == 1
    assert browser_page.locator('#events_table', has_text=XSS).count() == 1
    assert_not_executed(page, browser_page)
