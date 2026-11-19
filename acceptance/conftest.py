"""Acceptance tests running against Puppetboard and PuppetDB started with
docker-compose.yml. The test data is stored in PuppetDB before the tests run.
"""
import uuid
from datetime import timedelta

import pytest
import requests

from helpers import (NODES, NOW, PUPPETBOARD_URL, PUPPETDB_URL,
                     catalog_command, facts_command, report_command, submit,
                     wait_for)


@pytest.fixture(scope='session', autouse=True)
def puppetdb_data():
    wait_for(f'{PUPPETDB_URL}/status/v1/services/puppetdb-status')
    wait_for(f'{PUPPETBOARD_URL}/status')

    for certname, run in sorted(NODES.items()):
        env = run['env']
        when = NOW - run.get('age', timedelta())
        uuids = (str(uuid.uuid4()), str(uuid.uuid4()))
        submit('replace_facts', 5, facts_command(certname, env, when))
        submit('replace_catalog', 9,
               catalog_command(certname, env, when, *uuids))
        submit('store_report', 8, report_command(certname, run, when, *uuids))


class Puppetboard:
    """HTTP client for the Puppetboard under test."""

    def __init__(self):
        self.session = requests.Session()

    def get(self, path, expected_status=200, **kwargs):
        rv = self.session.get(PUPPETBOARD_URL + path, timeout=60, **kwargs)
        assert rv.status_code == expected_status, \
            f'GET {path}: {rv.status_code}\n{rv.text[:2000]}'
        return rv

    def post(self, path, data, expected_status=200):
        rv = self.session.post(PUPPETBOARD_URL + path, data=data, timeout=60)
        assert rv.status_code == expected_status, \
            f'POST {path}: {rv.status_code}\n{rv.text[:2000]}'
        return rv

    def get_json(self, path, **kwargs):
        return self.get(path, **kwargs).json()


@pytest.fixture(scope='session')
def puppetboard():
    return Puppetboard()
