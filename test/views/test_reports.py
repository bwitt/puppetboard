import json

from bs4 import BeautifulSoup

from puppetboard import app
from test import MockDbQuery


def test_json_report_ok(client, mocker, input_data,
                        mock_puppetdb_environments,
                        mock_puppetdb_default_nodes):
    query_response = json.loads(input_data)

    query_data = {
        'reports': [
            {
                'validate': {
                    'data': query_response[:100],
                    'checks': {
                        'limit': 100,
                        'offset': 0
                    }
                }
            }
        ]
    }

    dbquery = MockDbQuery(query_data)

    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)
    app.puppetdb.last_total = 499

    rv = client.get('/reports/json')

    assert rv.status_code == 200
    result_json = json.loads(rv.data.decode('utf-8'))

    assert 'data' in result_json
    assert len(result_json['data']) == 100


def test_report_escapes_logs(client, mocker,
                             mock_puppetdb_environments):
    xss = '<script>alert(1)</script>'
    query_data = {
        'reports': [[
            {
                "hash": '1234567',
                "receive_time": '2022-05-11T04:00:00.000Z',
                "report_format": 12,
                "puppet_version": "1.2.3",
                "start_time": '1948-09-07T00:00:01.000Z',
                "end_time": '2022-05-11T04:00:00.000Z',
                "producer_timestamp": '2022-05-11T04:00:00.000Z',
                "producer": 'foobar',
                "transaction_uuid": 'foobar',
                "status": 'failed',
                "noop": False,
                "noop_pending": False,
                "environment": 'production',
                "configuration_version": '123',
                "certname": 'node-failed',
                "code_id": 'foobar',
                "catalog_uuid": 'foobar',
                "cached_catalog_status": 'not_used',
                "resource_events": [],
                "metrics": {"data": []},
                "logs": {"data": [{
                    "time": '2022-05-11T04:00:00.000Z',
                    "level": 'err',
                    "source": xss,
                    "tags": [xss],
                    "message": xss,
                    "file": xss,
                    "line": 1,
                }]},
            },
        ]],
        'events': [[
        ]]
    }

    # one response set per request below
    query_data = {k: v * 2 for k, v in query_data.items()}
    dbquery = MockDbQuery(query_data)
    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)

    for show_error_as in ['friendly', 'raw']:
        rv = client.get(f'/report/node-failed/1234567/{show_error_as}',
                        follow_redirects=True)
        assert rv.status_code == 200

        page = rv.data.decode('utf-8')
        logs = json.loads(page.split('var logs = ')[1].split('\n')[0])
        assert '<script>' not in logs[0]['message']
        assert '&lt;script&gt;' in logs[0]['message']


def test_reports__a_report(client, mocker,
                           mock_puppetdb_environments,
                           ):
    query_data = {
        'reports': [[
            {
                "hash": '1234567',
                "receive_time": '2022-05-11T04:00:00.000Z',
                "report_format": 12,
                "puppet_version": "1.2.3",
                "start_time": '1948-09-07T00:00:01.000Z',
                "end_time": '2022-05-11T04:00:00.000Z',
                "producer_timestamp": '2022-05-11T04:00:00.000Z',
                "producer": 'foobar',
                "transaction_uuid": 'foobar',
                "status": 'failed',
                "noop": False,
                "noop_pending": False,
                "environment": 'production',
                "configuration_version": '123',
                "certname": 'node-failed',
                "code_id": 'foobar',
                "catalog_uuid": 'foobar',
                "cached_catalog_status": 'not_used',
                "resource_events": [],
                "metrics": {"data": []},
                "logs": {"data": []},
            },
        ]],
        'events': [[
        ]]
    }

    dbquery = MockDbQuery(query_data)

    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)
    app.puppetdb.last_total = 499

    rv = client.get('/report/node-failed/1234567')
    assert rv.status_code == 200

    soup = BeautifulSoup(rv.data, 'html.parser')
    assert soup.title.contents[0] == 'Puppetboard'

    vals = soup.find_all('table', {"id": "logs_table"})
    assert len(vals) == 1

    vals = soup.find_all('table', {"id": "events_table"})
    assert len(vals) == 1
