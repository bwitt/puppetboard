import pytest

from helpers import NODES, NOW, PRODUCTION_NODES, soup


def overview_counts(page):
    return {
        status: int(page.select_one(f'h1.ui.{status}.header').contents[0])
        for status in ['failed', 'noop', 'changed', 'unchanged', 'unreported']
    }


def test_status(puppetboard):
    assert puppetboard.get('/status').text == 'OK'


def test_overview(puppetboard):
    page = soup(puppetboard.get('/'))

    assert overview_counts(page) == {
        'failed': 1, 'noop': 1, 'changed': 1, 'unchanged': 1, 'unreported': 1,
    }
    population, resources = [
        int(h.text) for h in page.select('h1.ui.darkblue.header')[:2]]
    assert population == len(PRODUCTION_NODES)
    assert resources == 4 * len(PRODUCTION_NODES)

    # all the nodes except the unchanged ones are listed
    listed = {a.text.strip() for a in page.select('a[href^="/node/"]')}
    assert listed == {'node-changed.example.com', 'node-failed.example.com',
                      'node-noop.example.com', 'node-unreported.example.com'}


def test_overview_staging(puppetboard):
    page = soup(puppetboard.get('/staging/'))

    assert overview_counts(page) == {
        'failed': 0, 'noop': 0, 'changed': 1, 'unchanged': 0, 'unreported': 0,
    }


def test_overview_all_environments(puppetboard):
    page = soup(puppetboard.get('/*/'))

    assert overview_counts(page) == {
        'failed': 2, 'noop': 1, 'changed': 2, 'unchanged': 1, 'unreported': 1,
    }
    population = int(page.select('h1.ui.darkblue.header')[0].text)
    assert population == len(NODES)


@pytest.mark.parametrize('env, expected', [
    ('production', {'failed': 1, 'noop': 1, 'changed': 1, 'unchanged': 1,
                    'unreported': 1}),
    ('*', {'failed': 2, 'noop': 1, 'changed': 2, 'unchanged': 1,
           'unreported': 1}),
])
def test_radiator(puppetboard, env, expected):
    stats = puppetboard.get_json(f'/{env}/radiator',
                                 headers={'Accept': 'application/json'})
    assert {status: stats[status] for status in expected} == expected

    page = soup(puppetboard.get(f'/{env}/radiator'))
    assert page.title.text == 'Puppetboard'


def test_daily_reports_chart(puppetboard):
    result = puppetboard.get_json('/daily_reports_chart.json')['result']

    days = {day['day']: (day['changed'], day['failed'], day['unchanged'])
            for day in result}
    assert len(days) == 8
    assert days[NOW.strftime('%Y-%m-%d')] == (1, 1, 2)
    unreported_age = NODES['node-unreported.example.com']['age']
    assert days[(NOW - unreported_age).strftime('%Y-%m-%d')] == (0, 0, 1)

    result = puppetboard.get_json(
        '/daily_reports_chart.json?certname=node-failed.example.com')['result']
    assert sum(day['failed'] for day in result) == 1
    assert sum(day['changed'] + day['unchanged'] for day in result) == 0


def test_not_found(puppetboard):
    puppetboard.get('/no/such/page', expected_status=404)


def test_unknown_environment(puppetboard):
    puppetboard.get('/no-such-env/nodes', expected_status=404)
