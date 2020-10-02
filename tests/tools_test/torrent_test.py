from unittest.mock import Mock, call, patch

import pytest
import torf

from upsies import errors
from upsies.tools.torrent import _make_file_tree, create


class File(str):
    def __new__(cls, string, size):
        self = super().__new__(cls, string)
        self.size = size
        return self

def test_make_file_tree():
    filetree = {
        'Top': {
            'a': File('a', 123),
            'b': {
                'c': File('c', 456),
                'd': File('d', 789),
            }
        }
    }
    assert _make_file_tree(filetree) == (
        (('Top', (
            ('a', 123),
            ('b', (
                ('c', 456),
                ('d', 789),
            ))
        ))),
    )


class Callable:
    def __eq__(self, other):
        return callable(other)

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_handles_existing_torrent_file(Torrent_mock, file_tree_mock, path_exists_mock):
    path_exists_mock.return_value = True
    init_cb = Mock()
    progress_cb = Mock()
    torrent_path = create(
        content_path='path/to/content',
        announce='http://announce.url',
        torrent_path='path/to/torrent',
        init_callback=init_cb,
        progress_callback=progress_cb,
    )
    assert torrent_path == 'path/to/torrent'
    assert Torrent_mock.call_args_list == []
    assert init_cb.call_args_list == []
    assert progress_cb.call_args_list == []

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_overwrites_existing_torrent_file(Torrent_mock, file_tree_mock, path_exists_mock):
    path_exists_mock.return_value = True
    init_cb = Mock()
    progress_cb = Mock()
    torrent_path = create(
        content_path='path/to/content',
        overwrite=True,
        announce='http://announce.url',
        torrent_path='path/to/torrent',
        init_callback=init_cb,
        progress_callback=progress_cb,
    )
    assert torrent_path == 'path/to/torrent'
    assert Torrent_mock.call_args_list == [call(
        path='path/to/content',
        trackers=(('http://announce.url',),),
        source=None,
        exclude_regexs=(),
        private=True,
    )]
    assert init_cb.call_args_list == [call(file_tree_mock.return_value)]
    assert Torrent_mock.return_value.write.call_args_list == [call('path/to/torrent', overwrite=True)]

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
@pytest.mark.parametrize('source, exclude', ((None, None),
                                             ('asdf', None),
                                             (None, ('a.*', '.*b')),
                                             ('foo', ('a.*', '.*b'))))
def test_create_passes_arguments_to_Torrent_class(Torrent_mock, file_tree_mock, path_exists_mock, source, exclude):
    path_exists_mock.side_effect = (False, True)
    create_kwargs = {
        'content_path' : 'path/to/content',
        'announce' : 'http://announce.url',
        'torrent_path' : 'path/to/torrent',
        'init_callback' : Mock(),
        'progress_callback' : Mock(),
    }
    if source:
        create_kwargs['source'] = source
    if exclude:
        create_kwargs['exclude'] = exclude
    torrent_path = create(**create_kwargs)
    assert torrent_path == 'path/to/torrent'
    assert Torrent_mock.call_args_list == [call(
        path='path/to/content',
        trackers=(('http://announce.url',),),
        source=source or None,
        exclude_regexs=exclude or (),
        private=True,
    )]

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_init_callback(Torrent_mock, file_tree_mock, path_exists_mock):
    path_exists_mock.side_effect = (False, True)
    file_tree_mock.return_value = 'beautiful tree'
    init_cb = Mock()
    torrent_path = create(
        content_path='path/to/content',
        announce='http://announce.url',
        torrent_path='path/to/torrent',
        init_callback=init_cb,
        progress_callback=Mock()
    )
    assert torrent_path == 'path/to/torrent'
    assert init_cb.call_args_list == [call('beautiful tree')]
    assert file_tree_mock.call_args_list == [call(Torrent_mock.return_value.filetree)]

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_generates_torrent(Torrent_mock, file_tree_mock, path_exists_mock):
    path_exists_mock.side_effect = (False, True)
    torrent_path = create(
        content_path='path/to/content',
        announce='http://announce.url',
        torrent_path='path/to/torrent',
        init_callback=Mock(),
        progress_callback=Mock(),
    )
    assert torrent_path == 'path/to/torrent'
    assert Torrent_mock.return_value.generate.call_args_list == [call(
        callback=Callable(),
        interval=0.5,
    )]

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_catches_exception_from_torrent_generation(Torrent_mock, file_tree_mock, path_exists_mock):
    path_exists_mock.side_effect = (False, True)
    Torrent_mock.return_value.generate.side_effect = torf.TorfError('Nyet')
    with pytest.raises(errors.TorrentError, match=r'^Nyet$'):
        create(
            content_path='path/to/content',
            announce='http://announce.url',
            torrent_path='path/to/torrent',
            init_callback=Mock(),
            progress_callback=Mock(),
        )
    assert Torrent_mock.return_value.write.call_args_list == []

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_writes_torrent_file_after_successful_generation(Torrent_mock, file_tree_mock, path_exists_mock):
    path_exists_mock.side_effect = (False, True)
    torrent_path = create(
        content_path='path/to/content',
        announce='http://announce.url',
        torrent_path='path/to/torrent',
        init_callback=Mock(),
        progress_callback=Mock(),
    )
    assert torrent_path == 'path/to/torrent'
    assert Torrent_mock.return_value.write.call_args_list == [call('path/to/torrent', overwrite=False)]

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_does_not_accept_empty_announce_url(Torrent_mock, file_tree_mock, path_exists_mock):
    path_exists_mock.side_effect = (False, True)
    with pytest.raises(errors.TorrentError, match=r'^Announce URL is empty$'):
        create(
            content_path='path/to/content',
            announce='',
            torrent_path='path/to/torrent',
            init_callback=Mock(),
            progress_callback=Mock(),
        )
    assert Torrent_mock.call_args_list == []

@patch('upsies.tools.torrent._path_exists')
@patch('upsies.tools.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_catches_error_when_writing_torrent_file(Torrent_mock, file_tree_mock, path_exists_mock):
    path_exists_mock.side_effect = (False, True)
    Torrent_mock.return_value.write.side_effect = torf.TorfError('Nada')
    with pytest.raises(errors.TorrentError, match=r'^Nada$'):
        create(
            content_path='path/to/content',
            announce='http://announce.url',
            torrent_path='path/to/torrent',
            init_callback=Mock(),
            progress_callback=Mock(),
        )
    assert Torrent_mock.return_value.write.call_args_list == [call('path/to/torrent', overwrite=False)]
