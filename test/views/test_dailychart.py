import json
import time
from datetime import datetime, timezone

import pytest

from puppetboard import app
from test import MockDbQuery


def test_json_daily_reports_chart_ok(client, mocker,
                                     mock_puppetdb_environments,
                                     mock_puppetdb_default_nodes):
    query_data = {
        'reports': [
            [{'status': 'changed', 'count': 1}]
            for i in range(app.app.config['DAILY_REPORTS_CHART_DAYS'])
        ]
    }

    dbquery = MockDbQuery(query_data)

    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)

    rv = client.get('/daily_reports_chart.json')
    result_json = json.loads(rv.data.decode('utf-8'))

    assert 'result' in result_json
    assert (len(result_json['result']) ==
            app.app.config['DAILY_REPORTS_CHART_DAYS'])
    day_format = '%Y-%m-%d'
    cur_day = datetime.strptime(result_json['result'][0]['day'], day_format)
    for day in result_json['result'][1:]:
        next_day = datetime.strptime(day['day'], day_format)
        assert cur_day < next_day
        cur_day = next_day

    assert rv.status_code == 200


# one of these always has a different date than UTC
@pytest.mark.parametrize('tz', ['Etc/GMT+12', 'Etc/GMT-14'])
def test_json_daily_reports_chart_days_in_utc(client, mocker, monkeypatch, tz,
                                              mock_puppetdb_environments):
    days = app.app.config['DAILY_REPORTS_CHART_DAYS']
    query_data = {'reports': [[] for i in range(days)]}
    dbquery = MockDbQuery(query_data)
    mocker.patch.object(app.puppetdb, '_query', side_effect=dbquery.get)

    monkeypatch.setenv('TZ', tz)
    time.tzset()
    try:
        rv = client.get('/daily_reports_chart.json')
    finally:
        monkeypatch.undo()
        time.tzset()
    assert rv.status_code == 200

    result = json.loads(rv.data.decode('utf-8'))['result']
    assert result[-1]['day'] == datetime.now(timezone.utc).strftime('%Y-%m-%d')
