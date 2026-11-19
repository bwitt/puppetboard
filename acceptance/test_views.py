import json
import re

import pytest
from bs4 import BeautifulSoup

from helpers import MOTD_FILE, PRODUCTION_NODES, cell_text, link_href, soup


def test_catalogs(puppetboard):
    puppetboard.get('/catalogs')

    data = puppetboard.get_json('/catalogs/json')['data']
    assert sorted(cell_text(row[0]) for row in data) == PRODUCTION_NODES


def test_catalog(puppetboard):
    page = soup(puppetboard.get('/catalog/node-changed.example.com'))

    text = page.get_text()
    assert 'File[/etc/motd]' in text
    assert f'{MOTD_FILE}:3' in text
    assert 'Class[Profile::Web]' in text


def test_catalog_compare(puppetboard):
    compare_url = ('/catalogs/compare/'
                   'node-changed.example.com...node-failed.example.com')
    data = puppetboard.get_json(
        '/catalogs/compare/node-changed.example.com/json')['data']
    forms = [BeautifulSoup(row[2], 'html.parser').find('form')['action']
             for row in data]
    assert compare_url in forms

    page = soup(puppetboard.get(compare_url))
    nodes = page.select('table')[0].select('tbody tr td')[:2]
    assert [td.text for td in nodes] == ['node-changed.example.com',
                                         'node-failed.example.com']
    resources = [sorted(td.text for td in table.select('td'))
                 for table in page.select('table.catalog')[:2]]
    assert resources == [['Class[Main]', 'Class[Profile::Web]',
                          'File[/etc/motd]', 'Stage[main]']] * 2


def test_classes(puppetboard):
    puppetboard.get('/classes')

    data = puppetboard.get_json('/classes/json')['data']
    rows = {cell_text(row[0]): [cell_text(cell) for cell in row[1:]]
            for row in data}
    # nodes, then the failure, success and noop columns
    assert rows == {'Profile::Web': ['3', '1', '1', '1']}


def test_class_resource(puppetboard):
    url = link_href(puppetboard.get_json('/classes/json')['data'][0][0])
    puppetboard.get(url)

    data = puppetboard.get_json(url + '/json')['data']
    rows = {cell_text(row[0]): (cell_text(row[1]), cell_text(row[2]))
            for row in data}
    assert rows == {
        'node-changed.example.com': ('CHANGED', 'SUCCESS'),
        'node-failed.example.com': ('FAILED', 'FAILURE'),
        'node-noop.example.com': ('NOOP', 'NOOP'),
    }


def run_query(puppetboard, query, endpoint='pql', rawjson=False):
    page = soup(puppetboard.get('/query'))
    form = {
        'csrf_token': page.find('input', {'name': 'csrf_token'})['value'],
        'query': query,
        'endpoints': endpoint,
    }
    if rawjson:
        form['rawjson'] = 'y'
    return puppetboard.post('/query', form)


def test_query_pql(puppetboard):
    query = 'nodes[certname] { latest_report_status = "failed" }'
    page = run_query(puppetboard, query).text

    rows = json.loads(re.search(r'var data = (.*);', page).group(1))
    assert rows == [['node-failed.example.com']]


@pytest.mark.parametrize('endpoint, query', [
    ('nodes', '["=", "latest_report_status", "failed"]'),
    # AST queries are wrapped in [] if needed
    ('nodes', '"=", "latest_report_status", "failed"'),
])
def test_query_ast_raw_json(puppetboard, endpoint, query):
    page = run_query(puppetboard, query, endpoint, rawjson=True).text

    result = json.loads(re.search(r'pretty_print\((\[.*\])\)', page).group(1))
    assert [node['certname'] for node in result] == ['node-failed.example.com']


def test_query_error(puppetboard):
    page = soup(run_query(puppetboard, 'nodes[certname] { no_such_field = 1 }'))
    assert 'no_such_field' in page.find(id='invalid_query').text
