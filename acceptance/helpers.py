"""Test data stored in PuppetDB and helpers for the acceptance tests."""
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

PUPPETBOARD_URL = os.getenv('PUPPETBOARD_URL', 'http://localhost:8000')
PUPPETDB_URL = os.getenv('PUPPETDB_URL', 'http://localhost:8080')

NOW = datetime.now(timezone.utc).replace(microsecond=0)

# certname -> the run to store for it
NODES = {
    'node-changed.example.com':
        {'env': 'production', 'status': 'changed', 'event': 'success'},
    'node-failed.example.com':
        {'env': 'production', 'status': 'failed', 'event': 'failure'},
    'node-noop.example.com':
        {'env': 'production', 'status': 'unchanged', 'event': 'noop'},
    'node-unchanged.example.com':
        {'env': 'production', 'status': 'unchanged', 'event': None},
    'node-unreported.example.com':
        {'env': 'production', 'status': 'unchanged', 'event': None,
         'age': timedelta(days=1)},
    'node-staging.example.com':
        {'env': 'staging', 'status': 'changed', 'event': 'success'},
}
PRODUCTION_NODES = sorted(n for n, d in NODES.items()
                          if d['env'] == 'production')

CONFIGURATION_VERSION = '1700000000'
FAILURE_MESSAGE = ("change from 'absent' to 'file' failed: "
                   "Permission denied @ rb_sysopen - /etc/motd")
MOTD_FILE = ('/etc/puppetlabs/code/environments/production'
             '/modules/profile/manifests/web.pp')
OS_DESCRIPTION = 'Ubuntu 22.04.4 LTS'
PATH_FACT = '/usr/local/bin:/usr/bin:/bin'
# stored XSS attempt, the browser tests check that it is not executed
XSS_FACT = '<img src=x onerror="window.xss = true">'


def timestamp(when):
    return when.isoformat().replace('+00:00', 'Z')


def facts_command(certname, env, when):
    hostname = certname.split('.')[0]
    return {
        'certname': certname,
        'environment': env,
        'producer_timestamp': timestamp(when),
        'producer': 'puppet.example.com',
        'values': {
            'kernelrelease': '5.15.0-100-generic',
            'puppetversion': '8.10.0',
            'osfamily': 'Debian',
            'lsbdistdescription': OS_DESCRIPTION,
            'path': PATH_FACT,
            'banner': XSS_FACT,
            'os': {
                'name': 'Ubuntu',
                'family': 'Debian',
                'architecture': 'amd64',
                'release': {'full': '22.04', 'major': '22.04'},
                'distro': {'description': OS_DESCRIPTION},
            },
            'networking': {
                'hostname': hostname,
                'fqdn': certname,
                'ip': '192.0.2.%d' % (sorted(NODES).index(certname) + 1),
            },
            'trusted': {
                'certname': certname,
                'hostname': hostname,
                'domain': 'example.com',
                'authenticated': 'remote',
                'extensions': {},
            },
        },
    }


def catalog_command(certname, env, when, transaction_uuid, catalog_uuid):
    def resource(type_, title, **kwargs):
        return {'type': type_, 'title': title, 'exported': False,
                'tags': [type_.lower()], 'parameters': {}, **kwargs}

    def contains(source, target):
        return {'source': {'type': source[0], 'title': source[1]},
                'target': {'type': target[0], 'title': target[1]},
                'relationship': 'contains'}

    return {
        'certname': certname,
        'version': CONFIGURATION_VERSION,
        'environment': env,
        'transaction_uuid': transaction_uuid,
        'catalog_uuid': catalog_uuid,
        'producer_timestamp': timestamp(when),
        'producer': 'puppet.example.com',
        'code_id': None,
        'job_id': None,
        'resources': [
            resource('Stage', 'main'),
            resource('Class', 'Main'),
            resource('Class', 'Profile::Web'),
            resource('File', '/etc/motd', file=MOTD_FILE, line=3,
                     parameters={'ensure': 'file', 'content': 'Hello'}),
        ],
        'edges': [
            contains(('Stage', 'main'), ('Class', 'Main')),
            contains(('Stage', 'main'), ('Class', 'Profile::Web')),
            contains(('Class', 'Profile::Web'), ('File', '/etc/motd')),
        ],
    }


def report_command(certname, run, when, transaction_uuid, catalog_uuid):
    event_status = run['event']
    events = []
    logs = [{
        'file': None, 'line': None, 'level': 'notice', 'source': 'Puppet',
        'tags': ['notice'], 'time': timestamp(when),
        'message': 'Applied catalog in 0.42 seconds',
    }]
    if event_status:
        message = {
            'success': "defined content as '{sha256}abc'",
            'failure': FAILURE_MESSAGE,
            'noop': "current_value 'absent', should be 'file' (noop)",
        }[event_status]
        events.append({
            'status': event_status, 'timestamp': timestamp(when),
            'name': 'content_changed', 'property': 'ensure',
            'old_value': 'absent', 'new_value': 'file',
            'corrective_change': False, 'message': message,
        })
        logs.insert(0, {
            'file': MOTD_FILE, 'line': 3,
            'level': 'err' if event_status == 'failure' else 'notice',
            'source': '/Stage[main]/Profile::Web/File[/etc/motd]/ensure',
            'tags': ['file', 'class', 'profile::web'],
            'time': timestamp(when), 'message': message,
        })

    count = {status: int(event_status == status)
             for status in ['success', 'failure', 'noop']}
    metrics = [
        {'category': 'resources', 'name': 'total', 'value': 4},
        {'category': 'resources', 'name': 'skipped', 'value': 0},
        {'category': 'resources', 'name': 'changed',
         'value': count['success']},
        {'category': 'resources', 'name': 'failed', 'value': count['failure']},
        {'category': 'resources', 'name': 'out_of_sync',
         'value': len(events)},
        {'category': 'events', 'name': 'total', 'value': len(events)},
        {'category': 'events', 'name': 'success', 'value': count['success']},
        {'category': 'events', 'name': 'failure', 'value': count['failure']},
        {'category': 'events', 'name': 'noop', 'value': count['noop']},
        {'category': 'changes', 'name': 'total', 'value': count['success']},
        {'category': 'time', 'name': 'total', 'value': 0.42},
    ]
    return {
        'certname': certname,
        'environment': run['env'],
        'puppet_version': '8.10.0',
        'report_format': 12,
        'configuration_version': CONFIGURATION_VERSION,
        'start_time': timestamp(when - timedelta(seconds=10)),
        'end_time': timestamp(when),
        'producer_timestamp': timestamp(when),
        'producer': 'puppet.example.com',
        'transaction_uuid': transaction_uuid,
        'catalog_uuid': catalog_uuid,
        'code_id': None,
        'job_id': None,
        'cached_catalog_status': 'not_used',
        'status': run['status'],
        'noop': event_status == 'noop',
        'noop_pending': event_status == 'noop',
        'corrective_change': False,
        'type': 'agent',
        'logs': logs,
        'metrics': metrics,
        'resources': [{
            'skipped': False, 'timestamp': timestamp(when),
            'resource_type': 'File', 'resource_title': '/etc/motd',
            'file': MOTD_FILE, 'line': 3,
            'containment_path': ['Stage[main]', 'Profile::Web',
                                 'File[/etc/motd]'],
            'corrective_change': False, 'events': events,
        }] if events else [],
    }


def submit(command, version, payload):
    rv = requests.post(f'{PUPPETDB_URL}/pdb/cmd/v1', json=payload, params={
        'command': command,
        'version': version,
        'certname': payload['certname'],
        'producer-timestamp': payload['producer_timestamp'],
        'secondsToWaitForCompletion': 30,
    }, timeout=60)
    what = f'{command} for {payload["certname"]}'
    assert rv.status_code == 200, f'{what}: {rv.status_code} {rv.text}'
    assert rv.json().get('processed'), f'{what} not processed: {rv.text}'


def wait_for(url, timeout=300):
    deadline = time.monotonic() + timeout
    while True:
        try:
            if requests.get(url, timeout=5).ok:
                return
        except requests.ConnectionError:
            pass
        assert time.monotonic() < deadline, f'{url} is not available'
        time.sleep(2)


def soup(rv):
    return BeautifulSoup(rv.text, 'html.parser')


def cell_text(html):
    """Text of a DataTables cell, that may contain HTML."""
    return BeautifulSoup(str(html), 'html.parser').get_text(strip=True)


def link_href(html):
    """Target of the link in a DataTables cell."""
    return BeautifulSoup(str(html), 'html.parser').find('a')['href']
