import json
from types import SimpleNamespace

from bs4 import BeautifulSoup
from pypuppetdb.types import Node

from puppetboard import app
from puppetboard.schedulers.classes import build_async_cache
from puppetboard.views import classes as classes_view
from test import MockDbQuery

import pprint
import logging


def test_classes_disabled(client, mocker,
                          mock_puppetdb_environments,
                          mock_puppetdb_default_nodes):
    app.app.config['ENABLE_CLASS'] = False
    rv = client.get('/classes')
    assert rv.status_code == 403


def test_classes_view(client, mocker,
                      mock_puppetdb_environments,
                      mock_puppetdb_default_nodes):
    app.app.config['ENABLE_CLASS'] = True

    rv = client.get('/classes')
    assert rv.status_code == 200
    soup = BeautifulSoup(rv.data, 'html.parser')
    assert soup.title.contents[0] == 'Puppetboard'


def test_class_resource_view(client, mocker,
                             mock_puppetdb_environments,
                             mock_puppetdb_default_nodes):
    app.app.config['ENABLE_CLASS'] = True

    rv = client.get('/class_resource/My::Class')
    assert rv.status_code == 200

    soup = BeautifulSoup(rv.data, 'html.parser')
    assert soup.title.contents[0] == 'Puppetboard'
    vals = soup.find_all('h1', {"id": "class_name"})
    assert len(vals) == 1
    assert 'My::Class' in vals[0].string


def _class_node(*args, **kwargs):
    return iter([Node('_', 'node-1', latest_report_hash='report-1',
                      report_timestamp='2013-08-01T09:57:00.000Z',
                      status_report='changed')])


def _class_events(*args, **kwargs):
    return iter([SimpleNamespace(item={'class': 'Foo'}, status='success'),
                 SimpleNamespace(item={'class': 'Bar'}, status='success'),
                 SimpleNamespace(item={'class': None}, status='success')])


def _class_names(rv):
    assert rv.status_code == 200
    return sorted(BeautifulSoup(line[0], 'html.parser').text
                  for line in json.loads(rv.data.decode('utf-8'))['data'])


def test_classes_json_after_class_resource_json(client, mocker,
                                                mock_puppetdb_environments):
    app.app.config['ENABLE_CLASS'] = True
    classes_view.cache.clear()
    mocker.patch.object(app.puppetdb, 'nodes', side_effect=_class_node)
    mocker.patch.object(classes_view, 'get_events', side_effect=_class_events)

    rv = client.get('/class_resource/Foo/json')
    assert rv.status_code == 200
    assert len(json.loads(rv.data.decode('utf-8'))['data']) == 1

    # viewing a single class must not hide the other classes of the same report
    assert _class_names(client.get('/classes/json')) == ['Bar', 'Foo']
    # ...also when using the cache filled by the previous request
    assert _class_names(client.get('/classes/json')) == ['Bar', 'Foo']


def test_build_async_cache(client, mocker, mock_puppetdb_environments):
    classes_view.cache.clear()
    report = SimpleNamespace(hash_='report-1', node='node-1', status='changed',
                             events=_class_events)
    reports = mocker.patch.object(app.puppetdb, 'reports',
                                  side_effect=lambda *a, **kw: iter([report]))

    build_async_cache()

    for call in reports.call_args_list:
        assert '["=", "environment", ' in str(call.kwargs['query'])
    cached = classes_view.cache.get('classes_resource_production')
    assert sorted(cached) == ['Bar', 'Foo']

    # the classes view can use the cache filled by the scheduler
    app.app.config['ENABLE_CLASS'] = True
    mocker.patch.object(app.puppetdb, 'nodes', side_effect=_class_node)
    get_events = mocker.patch.object(classes_view, 'get_events')
    assert _class_names(client.get('/classes/json')) == ['Bar', 'Foo']
    get_events.assert_not_called()
