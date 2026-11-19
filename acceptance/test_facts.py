import json
import re

import pytest

from helpers import (OS_DESCRIPTION, PATH_FACT, PRODUCTION_NODES, cell_text,
                     soup)


def test_facts(puppetboard):
    page = soup(puppetboard.get('/facts'))

    links = {a.text.strip() for a in page.select('#fact-list a')}
    assert {'kernelrelease', 'lsbdistdescription', 'networking', 'os',
            'path', 'trusted'} <= links


@pytest.mark.parametrize('fact, value', [
    ('kernelrelease', '5.15.0-100-generic'),
    ('os.name', 'Ubuntu'),
])
def test_fact(puppetboard, fact, value):
    puppetboard.get(f'/fact/{fact}')

    data = puppetboard.get_json(f'/fact/{fact}/json')['data']
    assert sorted(cell_text(node) for node, _ in data) == PRODUCTION_NODES
    assert {json.loads(link_value)[1] for _, link_value in data} == {value}


def test_fact_chart(puppetboard):
    # osfamily is in GRAPH_FACTS
    chart = puppetboard.get_json('/fact/osfamily/json')['chart']
    assert chart == [{'label': 'Debian', 'value': len(PRODUCTION_NODES)}]


@pytest.mark.parametrize('fact, value', [
    ('kernelrelease', '5.15.0-100-generic'),
    ('lsbdistdescription', OS_DESCRIPTION),
    ('path', PATH_FACT),
])
def test_fact_value_link(puppetboard, fact, value):
    data = puppetboard.get_json(f'/fact/{fact}/json')['data']
    url, link_value = json.loads(data[0][1])
    assert link_value == value

    # the fact value page lists the nodes with this value
    page = puppetboard.get(url).text
    ajax_url = re.search(r'"ajax": "([^"]+)"', page).group(1)
    data = puppetboard.get_json(ajax_url)['data']
    assert sorted(cell_text(row[0]) for row in data) == PRODUCTION_NODES


def test_structured_fact_children(puppetboard):
    children = puppetboard.get_json('/fact/os/children/json')['children']
    assert {child['name']: child['has_children'] for child in children} == {
        'os.architecture': False, 'os.distro': True, 'os.family': False,
        'os.name': False, 'os.release': True,
    }
