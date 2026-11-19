import pytest

from helpers import NODES, PRODUCTION_NODES, cell_text, soup


def listed_nodes(page):
    return sorted(row.select('td')[1].text.strip()
                  for row in page.select('#main-table tbody tr'))


def test_nodes(puppetboard):
    assert listed_nodes(soup(puppetboard.get('/nodes'))) == PRODUCTION_NODES


def test_nodes_all_environments(puppetboard):
    assert listed_nodes(soup(puppetboard.get('/*/nodes'))) == sorted(NODES)


@pytest.mark.parametrize('status', ['failed', 'changed', 'unchanged',
                                    'noop', 'unreported'])
def test_nodes_status_filter(puppetboard, status):
    page = soup(puppetboard.get(f'/nodes?status={status}'))
    assert listed_nodes(page) == [f'node-{status}.example.com']


def test_node(puppetboard):
    page = soup(puppetboard.get('/node/node-changed.example.com'))
    assert page.find('b', string='node-changed.example.com')

    facts = puppetboard.get_json(
        '/node/node-changed.example.com/facts/json')['data']
    names = {name for name, value in facts}
    assert {'kernelrelease', 'os', 'networking', 'trusted'} <= names

    reports = puppetboard.get_json(
        '/reports/node-changed.example.com/json')['data']
    assert len(reports) == 1
    assert cell_text(reports[0][1]).startswith('CHANGED')


def test_unknown_node(puppetboard):
    puppetboard.get('/node/no-such-node.example.com', expected_status=404)


def test_failures(puppetboard):
    page = soup(puppetboard.get('/failures'))

    rows = page.select('#main-table tbody tr')
    assert len(rows) == 1
    assert 'node-failed.example.com' in rows[0].text
    assert 'Permission denied' in rows[0].text


def test_inventory(puppetboard):
    data = puppetboard.get_json('/inventory/json')['data']

    rows = {cell_text(row[0]): row for row in data}
    assert sorted(rows) == sorted(n.split('.')[0] for n in PRODUCTION_NODES)
    _, ip, os, arch, kernel, puppet_version = rows['node-changed']
    assert ip.startswith('192.0.2.')
    assert (os, arch, kernel, puppet_version) == (
        'Ubuntu', 'amd64', '5.15.0-100-generic', '8.10.0')
