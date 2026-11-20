from types import SimpleNamespace

from puppetboard import app


def test_failures_escapes_error(client, mocker,
                                mock_puppetdb_environments,
                                mock_puppetdb_default_nodes):
    xss = '<script>alert(1)</script>'
    report = SimpleNamespace(logs=[
        {'level': 'err', 'source': xss, 'message': xss},
    ])
    mocker.patch.object(app.puppetdb, 'reports',
                        side_effect=lambda *a, **kw: iter([report]))

    for show_error_as in ['friendly', 'raw']:
        rv = client.get(f'/failures/{show_error_as}', follow_redirects=True)
        assert rv.status_code == 200

        page = rv.data.decode('utf-8')
        assert xss not in page
        assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page
