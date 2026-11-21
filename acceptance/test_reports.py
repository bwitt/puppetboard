import json
import re

import pytest
from bs4 import BeautifulSoup

from helpers import (CONFIGURATION_VERSION, FAILURE_MESSAGE, PRODUCTION_NODES,
                     cell_text, link_href, soup)


def html_text(html):
    return BeautifulSoup(html, 'html.parser').get_text()


def reports_json(puppetboard, path='/reports/json', **params):
    params = {'draw': 1, 'start': 0, 'length': 100, **params}
    return puppetboard.get_json(path, params=params)


def page_variable(page, name):
    return json.loads(re.search(rf'var {name} = (.*)\n', page).group(1))


def test_reports(puppetboard):
    puppetboard.get('/reports')

    result = reports_json(puppetboard)
    assert result['recordsTotal'] == len(PRODUCTION_NODES)
    rows = {cell_text(row[2]): row for row in result['data']}
    assert sorted(rows) == PRODUCTION_NODES
    assert cell_text(rows['node-failed.example.com'][1]).startswith('FAILED')
    assert rows['node-failed.example.com'][3] == CONFIGURATION_VERSION
    assert rows['node-failed.example.com'][4] == '8.10.0'


@pytest.mark.parametrize('status, expected', [
    ('failed', ['node-failed.example.com']),
    ('changed', ['node-changed.example.com']),
    ('noop', ['node-noop.example.com']),
    ('unchanged', ['node-unchanged.example.com',
                   'node-unreported.example.com']),
])
def test_reports_status_filter(puppetboard, status, expected):
    result = reports_json(puppetboard,
                          **{'columns[1][search][value]': status})
    assert sorted(cell_text(row[2]) for row in result['data']) == expected


def test_reports_search(puppetboard):
    result = reports_json(puppetboard,
                          **{'search[value]': 'node-(changed|failed)'})
    assert sorted(cell_text(row[2]) for row in result['data']) == [
        'node-changed.example.com', 'node-failed.example.com']


def test_report(puppetboard):
    row = reports_json(puppetboard,
                       '/reports/node-failed.example.com/json')['data'][0]
    report_url = link_href(row[1])

    rv = puppetboard.get(report_url)
    assert CONFIGURATION_VERSION in soup(rv).get_text()
    page = rv.text

    logs = page_variable(page, 'logs')
    assert [log['level'] for log in logs] == ['err', 'notice']
    assert FAILURE_MESSAGE in html_text(logs[0]['message'])

    events = page_variable(page, 'events')
    assert events == [{'resource': 'File[/etc/motd]', 'status': 'failure',
                       'old': 'absent', 'new': 'file', 'failed': True}]

    # raw error messages
    page = puppetboard.get(report_url + '/raw').text
    logs = page_variable(page, 'logs')
    assert FAILURE_MESSAGE in html_text(logs[0]['message'])
