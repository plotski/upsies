from upsies.utils.scene import common


def test_SceneQuery_keywords():
    query = common.SceneQuery('foo bar', 'baz', '', '  ', 21)
    assert query.keywords == ('foo', 'bar', 'baz', '21')


def test_SceneQuery_group():
    query = common.SceneQuery(group='ASDF')
    assert query.group == 'ASDF'


def test_SceneQuery_from_release():
    release = {
        'title': 'The Foo',
        'year': '2004',
        'resolution': '720p',
        'source': 'BluRay',
        'video_codec': 'x264',
        'group': 'ASDF',
    }
    query = common.SceneQuery.from_release(release)
    assert query.keywords == ('The', 'Foo', '2004', '720p', 'BluRay', 'x264')
    assert query.group == 'ASDF'


def test_SceneQuery_from_string():
    query = common.SceneQuery.from_string('The.Foo.2004.720p.BluRay.x264-ASDF')
    assert query.keywords == ('The', 'Foo', '2004', '720p', 'BluRay', 'x264')
    assert query.group == 'ASDF'


def test_SceneQuery_repr():
    assert repr(common.SceneQuery('foo', 'bar', 'baz')) == "SceneQuery('foo', 'bar', 'baz')"
    assert repr(common.SceneQuery(group='ASDF')) == "SceneQuery(group='ASDF')"
    assert repr(common.SceneQuery('foo', 'bar', group='ASDF')) == "SceneQuery('foo', 'bar', group='ASDF')"
