from unittest.mock import Mock, call, patch

import pytest
import torf

from upsies import __project_name__, __version__, errors
from upsies.utils.torrent import (_CreateTorrentCallbackWrapper,
                                  _make_file_tree, create)


class Callable:
    def __eq__(self, other):
        return callable(other)

@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_handles_existing_torrent_file(Torrent_mock, file_tree_mock, tmp_path):
    torrent_path = tmp_path / 'file.torrent'
    torrent_path.write_bytes(b'asdf')
    init_cb = Mock()
    progress_cb = Mock()
    return_value = create(
        content_path='path/to/content',
        announce='http://announce.url',
        torrent_path=torrent_path,
        init_callback=init_cb,
        progress_callback=progress_cb,
    )
    assert return_value == torrent_path
    assert Torrent_mock.call_args_list == []
    assert init_cb.call_args_list == []
    assert progress_cb.call_args_list == []

@patch('time.time')
@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_overwrites_existing_torrent_file(Torrent_mock, file_tree_mock, time_mock, tmp_path):
    torrent_path = tmp_path / 'file.torrent'
    torrent_path.write_bytes(b'asdf')
    init_cb = Mock()
    progress_cb = Mock()
    return_value = create(
        content_path='path/to/content',
        overwrite=True,
        announce='http://announce.url',
        torrent_path=torrent_path,
        init_callback=init_cb,
        progress_callback=progress_cb,
    )
    assert return_value == torrent_path
    assert Torrent_mock.call_args_list == [call(
        path='path/to/content',
        exclude_regexs=(),
        trackers=(('http://announce.url',),),
        private=True,
        source=None,
        created_by=f'{__project_name__} {__version__}',
        creation_date=time_mock.return_value,
    )]
    assert init_cb.call_args_list == [call(file_tree_mock.return_value)]
    assert Torrent_mock.return_value.write.call_args_list == [call(torrent_path, overwrite=True)]

@patch('time.time')
@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
@pytest.mark.parametrize(
    argnames='source, exclude',
    argvalues=(
        (None, None),
        ('asdf', None),
        (None, ('a.*', '.*b')),
        ('foo', ('a.*', '.*b')),
    ),
)
def test_create_passes_arguments_to_Torrent_class(Torrent_mock, file_tree_mock, time_mock, source, exclude):
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
    return_value = create(**create_kwargs)
    assert return_value == 'path/to/torrent'
    assert Torrent_mock.call_args_list == [call(
        path='path/to/content',
        exclude_regexs=exclude or (),
        trackers=(('http://announce.url',),),
        private=True,
        source=source or None,
        created_by=f'{__project_name__} {__version__}',
        creation_date=time_mock.return_value,
    )]

@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_calls_init_callback(Torrent_mock, file_tree_mock):
    file_tree_mock.return_value = 'beautiful tree'
    init_cb = Mock()
    return_value = create(
        content_path='path/to/content',
        announce='http://announce.url',
        torrent_path='path/to/torrent',
        init_callback=init_cb,
        progress_callback=Mock()
    )
    assert return_value == 'path/to/torrent'
    assert init_cb.call_args_list == [call('beautiful tree')]
    assert file_tree_mock.call_args_list == [call(Torrent_mock.return_value.filetree)]

@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_generates_torrent(Torrent_mock, file_tree_mock):
    return_value = create(
        content_path='path/to/content',
        announce='http://announce.url',
        torrent_path='path/to/torrent',
        init_callback=Mock(),
        progress_callback=Mock(),
    )
    assert return_value == 'path/to/torrent'
    assert Torrent_mock.return_value.generate.call_args_list == [call(
        callback=Callable(),
        interval=1.0,
    )]

@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_catches_exception_from_torrent_generation(Torrent_mock, file_tree_mock):
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

@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_does_not_accept_empty_announce_url(Torrent_mock, file_tree_mock):
    with pytest.raises(errors.TorrentError, match=r'^Announce URL is empty$'):
        create(
            content_path='path/to/content',
            announce='',
            torrent_path='path/to/torrent',
            init_callback=Mock(),
            progress_callback=Mock(),
        )
    assert Torrent_mock.call_args_list == []

@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_catches_error_when_writing_torrent_file(Torrent_mock, file_tree_mock):
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

@patch('upsies.utils.torrent._make_file_tree')
@patch('torf.Torrent')
def test_create_writes_torrent_file_after_successful_generation(Torrent_mock, file_tree_mock):
    Torrent_mock.return_value.generate.return_value = True
    return_value = create(
        content_path='path/to/content',
        announce='http://announce.url',
        torrent_path='path/to/torrent',
        init_callback=Mock(),
        progress_callback=Mock(),
    )
    assert return_value == 'path/to/torrent'
    assert Torrent_mock.return_value.write.call_args_list == [call('path/to/torrent', overwrite=False)]


def test_make_file_tree():
    class File(str):
        def __new__(cls, string, size):
            self = super().__new__(cls, string)
            self.size = size
            return self

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


def test_CreateTorrentCallbackWrapper(mocker):
    progress_cb = Mock()
    cbw = _CreateTorrentCallbackWrapper(progress_cb)
    pieces_total = 12
    for pieces_done in range(0, pieces_total + 1):
        return_value = cbw(Mock(piece_size=450, size=5000), 'current/file', pieces_done, pieces_total)
        assert return_value is progress_cb.return_value
        status = progress_cb.call_args[0][0]
        assert status.percent_done == max(0, min(100, pieces_done / pieces_total * 100))
        assert status.piece_size == 450
        assert status.total_size == 5000
        assert status.pieces_done == pieces_done
        assert status.pieces_total == pieces_total
        assert status.filepath == 'current/file'

        # TODO: If you're a Python wizard, feel free to attempt at adding tests
        #       for these CreateTorrentStatus attributes: seconds_elapsed,
        #       seconds_remaining, seconds_total, time_finished, time_started
