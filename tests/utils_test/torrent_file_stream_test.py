import re
from unittest.mock import Mock, PropertyMock, call

import pytest

from upsies import errors
from upsies.utils.torrent import TorrentFileStream


class File(str):
    byte_counter = 0

    def __new__(cls, path, size):
        self = super().__new__(cls, path)
        self.size = size
        self.content = bytearray()
        for _ in range(0, size):
            self.content += type(self).byte_counter.to_bytes(1, byteorder='big')
            if type(self).byte_counter >= 255:
                type(self).byte_counter = 0
            else:
                type(self).byte_counter += 1
        return self

    def write_at(self, directory, content=None):
        if content is not None:
            (directory / self).write_bytes(content)
        else:
            (directory / self).write_bytes(self.content)


class Torrent:
    def __init__(self, files, piece_size):
        self.files = files
        self.piece_size = piece_size
        self.size = sum(f.size for f in files)
        self.pieces = int(self.size / piece_size) + 1


def test_behaviour_as_context_manager(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    mocked_open_files = [Mock(), Mock(), Mock()]
    with tfs as x:
        assert x is tfs
        for i,mof in enumerate(mocked_open_files):
            tfs._open_files[f'path/to/{i}'] = mof
    for mof in mocked_open_files:
        assert mof.close.call_args_list == [call()]
    assert tfs._open_files == {}


def test_get_file_position(tmp_path):
    torrent = Torrent(
        piece_size=12,
        files=(
            File('foo', size=12),
            File('bar', size=15),
            File('baz', size=24),
            File('bam', size=5),
        ),
    )
    tfs = TorrentFileStream(torrent, location=tmp_path)
    assert tfs.get_file_position(torrent.files[0]) == 0
    assert tfs.get_file_position(torrent.files[1]) == 12
    assert tfs.get_file_position(torrent.files[2]) == 27
    assert tfs.get_file_position(torrent.files[3]) == 51


@pytest.mark.parametrize(
    argnames='files, position, exp_filename, exp_error',
    argvalues=(
        # 0   1   2   3   4   5
        # aaabbbbbcccccccdddddd
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)),
         -1, None, 'byte_index is out of bounds (0 - 21): -1'),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 0, 'a', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 1, 'a', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 2, 'a', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 3, 'b', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 4, 'b', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 5, 'b', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 6, 'b', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 7, 'b', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 8, 'c', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 9, 'c', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 10, 'c', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 11, 'c', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 12, 'c', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 13, 'c', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 14, 'c', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 15, 'd', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 16, 'd', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 17, 'd', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 18, 'd', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 19, 'd', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)), 20, 'd', None),
        ((File('a', size=3), File('b', size=5), File('c', size=7), File('d', size=6)),
         21, None, 'byte_index is out of bounds (0 - 21): 21'),
    ),
)
def test_get_file_at_position(files, position, exp_filename, exp_error, tmp_path):
    torrent = Torrent(piece_size=4, files=files)
    tfs = TorrentFileStream(torrent, location=tmp_path)

    if exp_error:
        with pytest.raises(ValueError, match=rf'^{re.escape(exp_error)}$'):
            tfs.get_file_at_position(position)
    else:
        file = [f for f in files if f == exp_filename][0]
        assert tfs.get_file_at_position(position) == file


@pytest.mark.parametrize(
    argnames='files, exp_piece_indexes',
    argvalues=(
        ((File('foo', 11), File('bar', 48)), {'foo': [0], 'bar': [0, 1, 2, 3, 4]}),
        ((File('foo', 12), File('bar', 48)), {'foo': [0], 'bar': [1, 2, 3, 4]}),
        ((File('foo', 13), File('bar', 48)), {'foo': [0, 1], 'bar': [1, 2, 3, 4, 5]}),

        ((File('foo', 24), File('bar', 47)), {'foo': [0, 1], 'bar': [2, 3, 4, 5]}),
        ((File('foo', 24), File('bar', 48)), {'foo': [0, 1], 'bar': [2, 3, 4, 5]}),
        ((File('foo', 24), File('bar', 49)), {'foo': [0, 1], 'bar': [2, 3, 4, 5, 6]}),

        ((File('foo', 25), File('bar', 47)), {'foo': [0, 1, 2], 'bar': [2, 3, 4, 5]}),
        ((File('foo', 25), File('bar', 48)), {'foo': [0, 1, 2], 'bar': [2, 3, 4, 5, 6]}),

        ((File('foo', 35), File('bar', 47)), {'foo': [0, 1, 2], 'bar': [2, 3, 4, 5, 6]}),
        ((File('foo', 35), File('bar', 48)), {'foo': [0, 1, 2], 'bar': [2, 3, 4, 5, 6]}),
        ((File('foo', 35), File('bar', 49)), {'foo': [0, 1, 2], 'bar': [2, 3, 4, 5, 6]}),
        ((File('foo', 35), File('bar', 50)), {'foo': [0, 1, 2], 'bar': [2, 3, 4, 5, 6, 7]}),

        ((File('foo', 36), File('bar', 47)), {'foo': [0, 1, 2], 'bar': [3, 4, 5, 6]}),
        ((File('foo', 36), File('bar', 48)), {'foo': [0, 1, 2], 'bar': [3, 4, 5, 6]}),
        ((File('foo', 36), File('bar', 49)), {'foo': [0, 1, 2], 'bar': [3, 4, 5, 6, 7]}),
    ),
    ids=lambda v: str(v),
)
def test_get_piece_indexes_for_file(files, exp_piece_indexes, tmp_path):
    torrent = Torrent(piece_size=12, files=files)
    tfs = TorrentFileStream(torrent, location=tmp_path)
    for filename, exp_indexes in exp_piece_indexes.items():
        file = [f for f in torrent.files if f == filename][0]
        assert tfs.get_piece_indexes_for_file(file) == exp_indexes


@pytest.mark.parametrize(
    argnames='files, first_byte_indexes, last_byte_indexes, exp_files',
    argvalues=(
        ((File('a', 11), File('b', 49), File('c', 50)), range(0, 11), range(120, 121), ['a', 'b', 'c']),
        ((File('a', 11), File('b', 49), File('c', 50)), range(11, 60), range(120, 121), ['b', 'c']),
        ((File('a', 11), File('b', 49), File('c', 50)), range(60, 110), range(120, 121), ['c']),
        ((File('a', 11), File('b', 49), File('c', 50)), range(110, 120), range(120, 121), []),

        ((File('a', 11), File('b', 49), File('c', 50)), range(0, 1), range(60, 121), ['a', 'b', 'c']),
        ((File('a', 11), File('b', 49), File('c', 50)), range(0, 1), range(11, 60), ['a', 'b']),
        ((File('a', 11), File('b', 49), File('c', 50)), range(0, 1), range(0, 11), ['a']),

        ((File('a', 11), File('b', 49), File('c', 50)), range(0, 11), range(0, 11), ['a']),
        ((File('a', 11), File('b', 49), File('c', 50)), range(11, 60), range(11, 60), ['b']),
        ((File('a', 11), File('b', 49), File('c', 50)), range(60, 110), range(60, 110), ['c']),
        ((File('a', 11), File('b', 49), File('c', 50)), range(110, 120), range(110, 120), []),
    ),
    ids=lambda v: str(v),
)
def test_get_files_for_byte_range(first_byte_indexes, last_byte_indexes, files, exp_files, tmp_path):
    torrent = Torrent(piece_size=12, files=files)
    tfs = TorrentFileStream(torrent, location=tmp_path)
    first_byte_indexes = tuple(first_byte_indexes)
    last_byte_indexes = tuple(last_byte_indexes)
    assert first_byte_indexes, first_byte_indexes
    assert last_byte_indexes, last_byte_indexes
    for first_byte_index in first_byte_indexes:
        for last_byte_index in last_byte_indexes:
            if first_byte_index <= last_byte_index:
                assert tfs.get_files_for_byte_range(first_byte_index, last_byte_index) == exp_files


# @pytest.mark.parametrize(
#     argnames='file_before_size, file_after_size',
#     argvalues=(
#         (0, 0),
#         (11, 0), (12, 0), (13, 0),
#         (0, 11), (0, 12), (0, 13),
#         (11, 11), (12, 12), (13, 13),
#         (11, 12), (11, 13), (12, 13), (13, 12), (13, 11),
#     ),
# )
# @pytest.mark.parametrize(
#     argnames='file, wanted_piece_indexes, exp_indexes',
#     argvalues=(
#         (File('foo', 11), (0, 1, -1, -2), [0]),
#         (File('foo', 12), (0, 1, -1, -2), [0]),
#         (File('foo', 13), (0, 1, -1, -2), [0, 1]),

#         (File('foo', 239), (0, 1, -1, -2), [0, 1, 18, 19]),
#         (File('foo', 240), (0, 1, -1, -2), [0, 1, 18, 19]),
#         (File('foo', 241), (0, 1, -1, -2), [0, 1, 19, 20]),
#     ),
#     ids=lambda v: str(v),
# )
# def test_get_relative_piece_indexes(file, wanted_piece_indexes, exp_indexes, file_before_size, file_after_size, tmp_path):
#     files = (
#         File('before', size=file_before_size),
#         file,
#         File('after', size=file_after_size),
#     )
#     torrent = Torrent(piece_size=12, files=files)
#     tfs = TorrentFileStream(torrent, location=tmp_path)
#     assert tfs.get_relative_piece_indexes(file, wanted_piece_indexes) == exp_indexes


@pytest.mark.parametrize(
    argnames='piece_size, files, file, relative_piece_indexes, exp_absolute_indexes',
    argvalues=(
        # First piece contains multiple files
        # 0     1     2     3     4     5     6     7     8     9     0
        # aabbbcccccccccccccccccccccccccccccccccccccccccccccccccc
        (6, (File('a', size=2), File('b', size=3), File('c', size=50)), 'a', (0, 1, 1000, -1, -2, -1000), [0]),
        (6, (File('a', size=2), File('b', size=3), File('c', size=50)), 'b', (0, 1, 1000, -1, -2, -1000), [0]),
        (6, (File('a', size=2), File('b', size=3), File('c', size=50)), 'c', (0, 1, 1000, -1, -2, -1000), [0, 1, 8, 9]),

        # Middle piece contains multiple files
        # 0     1     2     3     4     5     6     7     8     9     0
        # aaaaaaaaaaaaabbcccdddddddddddddddddddddddddddddddddddd
        (6, (File('a', 13), File('b', 2), File('c', 3), File('d', 36)), 'a', (0, 1, 1000, -1, -2, -1000), [0, 1, 2]),
        (6, (File('a', 13), File('b', 2), File('c', 3), File('d', 36)), 'b', (0, 1, 1000, -1, -2, -1000), [2]),
        (6, (File('a', 13), File('b', 2), File('c', 3), File('d', 36)), 'c', (0, 1, 1000, -1, -2, -1000), [2]),
        (6, (File('a', 13), File('b', 2), File('c', 3), File('d', 36)), 'd', (0, 1, 1000, -1, -2, -1000), [3, 4, 7, 8]),

        # Last piece contains multiple files
        # 0     1     2     3     4     5     6     7     8     9     0
        # aaaaaaaaaaaaaaaaaaaaaaaaaaaaaabbcddd
        (6, (File('a', 30), File('b', 2), File('c', 1), File('d', 3)), 'a', (0, 1, 1000, -1, -2, -1000), [0, 1, 3, 4]),
        (6, (File('a', 30), File('b', 2), File('c', 1), File('d', 3)), 'b', (0, 1, 1000, -1, -2, -1000), [5]),
        (6, (File('a', 30), File('b', 2), File('c', 1), File('d', 3)), 'c', (0, 1, 1000, -1, -2, -1000), [5]),
        (6, (File('a', 30), File('b', 2), File('c', 1), File('d', 3)), 'd', (0, 1, 1000, -1, -2, -1000), [5]),
    ),
    ids=lambda v: str(v),
)
def test_get_absolute_piece_indexes(piece_size, files, file, relative_piece_indexes, exp_absolute_indexes, tmp_path):
    torrent = Torrent(piece_size=piece_size, files=files)
    tfs = TorrentFileStream(torrent, location=tmp_path)
    file = [f for f in files if f == file][0]
    assert tfs.get_absolute_piece_indexes(file, relative_piece_indexes) == exp_absolute_indexes


@pytest.mark.parametrize(
    argnames='piece_size, files, piece_index',
    argvalues=(
        # 0     1     2     3     4     5     6     7
        # aaaaaaaaaaabbbbbbbbbbbbbcccccccddddddddddd
        (6, (File('a', size=11), File('b', size=13), File('c', size=7), File('d', size=11)), 0),
        (6, (File('a', size=11), File('b', size=13), File('c', size=7), File('d', size=11)), 1),
        (6, (File('a', size=11), File('b', size=13), File('c', size=7), File('d', size=11)), 2),
        (6, (File('a', size=11), File('b', size=13), File('c', size=7), File('d', size=11)), 3),
        (6, (File('a', size=11), File('b', size=13), File('c', size=7), File('d', size=11)), 4),
        (6, (File('a', size=11), File('b', size=13), File('c', size=7), File('d', size=11)), 5),
        (6, (File('a', size=11), File('b', size=13), File('c', size=7), File('d', size=11)), 6),

        # First piece contains multiple complete files
        # 0           1           2           3           4           5
        # aaaabbbbbccccccccccccccccccccccccccccccccccccccccccccccccccccc
        (12, (File('a', size=4), File('b', size=5), File('c', size=53)), 0),
        (12, (File('a', size=4), File('b', size=5), File('c', size=53)), 1),
        (12, (File('a', size=4), File('b', size=5), File('c', size=53)), 2),
        (12, (File('a', size=4), File('b', size=5), File('c', size=53)), 3),
        (12, (File('a', size=4), File('b', size=5), File('c', size=53)), 4),
        (12, (File('a', size=4), File('b', size=5), File('c', size=53)), 5),

        # Middle piece contains multiple complete files
        # 0              1              2              3
        # aaaaaaaaaaaaaaaaaaaaabbbbbcccdddddddddddddddddddd
        (15, (File('a', size=21), File('b', size=5), File('c', size=3), File('d', size=20)), 0),
        (15, (File('a', size=21), File('b', size=5), File('c', size=3), File('d', size=20)), 1),
        (15, (File('a', size=21), File('b', size=5), File('c', size=3), File('d', size=20)), 2),
        (15, (File('a', size=21), File('b', size=5), File('c', size=3), File('d', size=20)), 3),

        # Last piece contains multiple complete files
        # 0           1           2           3
        # aaaaaaaaaaaaaaaaaaaaaaaaaabbbbccccc
        (12, (File('a', size=26), File('b', size=4), File('c', size=5)), 0),
        (12, (File('a', size=26), File('b', size=4), File('c', size=5)), 1),
        (12, (File('a', size=26), File('b', size=4), File('c', size=5)), 2),
    ),
    ids=lambda v: str(v),
)
def test_get_piece_returns_piece_from_file(piece_size, files, piece_index, tmp_path):
    for f in files:
        print(f'{f}: {f.size} bytes: {f.content}')
        f.write_at(tmp_path)

    stream = b''.join(f.content for f in files)
    print('concatenated stream:', stream)
    start = piece_index * piece_size
    stop = min(start + piece_size, len(stream))
    exp_piece = stream[start:stop]
    print('exp_piece:', f'[{start}:{stop}]:', exp_piece)
    exp_piece_length = stop - start
    assert len(exp_piece) == exp_piece_length

    torrent = Torrent(piece_size=piece_size, files=files)
    with TorrentFileStream(torrent, location=tmp_path) as tfs:
        piece = tfs.get_piece(piece_index)
        assert piece == exp_piece

@pytest.mark.parametrize(
    argnames='piece_size, files, piece_index, exp_min_piece_index, exp_max_piece_index',
    argvalues=(
        # First file is smaller than one piece
        # 0           1           2           3           4           5           6           7
        # aaaaaaaaaaabbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbcccccccccccccccccccccccccccccc
        (12, (File('a', size=11), File('b', size=49), File('c', size=30)), -1, 0, 7),
        (12, (File('a', size=11), File('b', size=49), File('c', size=30)), 8, 0, 7),

        # Last file is smaller than one piece
        # 0   1   2   3   4   5   6   7
        # aaaaaaaabbbbbbbbbbbbbbbbbccc
        (4, (File('a', size=8), File('b', size=17), File('c', size=3)), -1, 0, 6),
        (4, (File('a', size=8), File('b', size=17), File('c', size=3)), 7, 0, 6),

        # First piece contains multiple complete files
        # 0           1           2           3           4           5           6
        # aaaabbbbbccccccccccccccccccccccccccccccccccccccccccccccccccccc
        (12, (File('a', size=4), File('b', size=5), File('c', size=53)), -1, 0, 5),
        (12, (File('a', size=4), File('b', size=5), File('c', size=53)), 6, 0, 5),

        # Middle piece contains multiple complete files
        # 0              1              2              3
        # aaaaaaaaaaaaaaaaaaaaabbbbbcccdddddddddddddddddddd
        (15, (File('a', size=21), File('b', size=5), File('c', size=3), File('d', size=20)), -1, 0, 3),
        (15, (File('a', size=21), File('b', size=5), File('c', size=3), File('d', size=20)), 4, 0, 3),

        # Last piece contains multiple complete files
        # 0           1           2           3
        # aaaaaaaaaaaaaaaaaaaaaaaaaabbbbccccc
        (12, (File('a', size=26), File('b', size=4), File('c', size=5)), -1, 0, 2),
        (12, (File('a', size=26), File('b', size=4), File('c', size=5)), 3, 0, 2),
    ),
    ids=lambda v: str(v),
)
def test_get_piece_raises_if_piece_index_is_out_of_bounds(piece_size, files, piece_index, exp_min_piece_index, exp_max_piece_index, tmp_path):
    torrent = Torrent(piece_size=piece_size, files=files)
    tfs = TorrentFileStream(torrent, location=tmp_path)
    with pytest.raises(ValueError, match=rf'^piece_index must be in range 0 - {exp_max_piece_index}: {piece_index}$'):
        tfs.get_piece(piece_index)

@pytest.mark.parametrize(
    argnames='files, missing_files, piece_index, exp_piece',
    argvalues=(
        # 0           1           2           3           4           5           6           7           8           9
        # aaaaaaaaaaabbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbcccccccccccccccccccccccccccccccccccccccccccc
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 0, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 1, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 2, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 3, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 4, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 5, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 6, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 7, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['a'], 8, bytes),

        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 0, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 1, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 2, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 3, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 4, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 5, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 6, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 7, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['b'], 8, bytes),

        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 0, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 1, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 2, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 3, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 4, bytes),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 5, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 6, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 7, None),
        ((File('a', size=11), File('b', size=49), File('c', size=44)), ['c'], 8, None),
    ),
    ids=lambda v: str(v),
)
def test_get_piece_returns_None_if_file_is_missing(files, missing_files, piece_index, exp_piece, tmp_path):
    for f in files:
        if f not in missing_files:
            print(f'writing {f}: {f.size} bytes: {f.content}')
            f.write_at(tmp_path)
        else:
            print(f'not writing {f}: {f.size} bytes: {f.content}')

    torrent = Torrent(piece_size=12, files=files)
    tfs = TorrentFileStream(torrent, location=tmp_path)
    if exp_piece is None:
        assert tfs.get_piece(piece_index) is None
    else:
        assert isinstance(tfs.get_piece(piece_index), bytes)


@pytest.mark.parametrize(
    argnames='piece_size, files, contents, piece_index, exp_piece',
    argvalues=(
        # 0     1     2     3     4     5
        # aaaaaaaaaaabbbbbbbbbbbbcccccc
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'a': b'x' * 10}, 0, None),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'a': b'x' * 10}, 1, None),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'a': b'x' * 10}, 2, bytes),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'a': b'x' * 10}, 3, bytes),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'a': b'x' * 10}, 4, bytes),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'b': b'x' * 14}, 0, bytes),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'b': b'x' * 14}, 1, None),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'b': b'x' * 14}, 2, None),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'b': b'x' * 14}, 3, None),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'b': b'x' * 14}, 4, bytes),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'c': b'x' * 20}, 0, bytes),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'c': b'x' * 20}, 1, bytes),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'c': b'x' * 20}, 2, bytes),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'c': b'x' * 20}, 3, None),
        (6, (File('a', size=11), File('b', size=12), File('c', size=6)), {'c': b'x' * 20}, 4, None),
    ),
    ids=lambda v: str(v),
)
def test_get_piece_returns_None_if_file_size_is_wrong(piece_size, files, contents, piece_index, exp_piece, tmp_path):
    for f in files:
        content = contents.get(f, f.content)
        print(f'{f}: {f.size} bytes: {content}, real size: {len(content)} bytes')
        f.write_at(tmp_path, content)

    if exp_piece is not None:
        stream = b''.join(f.content for f in files)
        print('concatenated stream:', stream)
        start = piece_index * piece_size
        stop = min(start + piece_size, len(stream))
        exp_piece = stream[start:stop]
        print('exp_piece:', f'[{start}:{stop}]:', exp_piece)
        exp_piece_length = stop - start
        assert len(exp_piece) == exp_piece_length

    torrent = Torrent(piece_size=piece_size, files=files)
    with TorrentFileStream(torrent, location=tmp_path) as tfs:
        assert tfs.get_piece(piece_index) == exp_piece


def test_get_file_size_from_fs_returns_file_size(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='path/to')
    exists_mock = mocker.patch('os.path.exists', return_value=True)
    getsize_mock = mocker.patch('os.path.getsize', return_value=123456)
    assert tfs._get_file_size_from_fs('b') == 123456
    assert exists_mock.call_args_list == [call('path/to/b')]
    assert getsize_mock.call_args_list == [call('path/to/b')]

def test_get_file_size_from_fs_gets_nonexisting_file(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='path/to')
    exists_mock = mocker.patch('os.path.exists', return_value=False)
    getsize_mock = mocker.patch('os.path.getsize', return_value=123456)
    assert tfs._get_file_size_from_fs('b') is None
    assert exists_mock.call_args_list == [call('path/to/b')]
    assert getsize_mock.call_args_list == []

def test_get_file_size_from_fs_gets_private_file(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='path/to')
    exists_mock = mocker.patch('os.path.exists', return_value=True)
    getsize_mock = mocker.patch('os.path.getsize', side_effect=PermissionError('Size is secret'))
    assert tfs._get_file_size_from_fs('b') is None
    assert exists_mock.call_args_list == [call('path/to/b')]
    assert getsize_mock.call_args_list == [call('path/to/b')]


def test_get_open_file_gets_nonexisting_file(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=False)
    open_mock = mocker.patch('__main__.open')
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    assert tfs._get_open_file('b') is None
    assert exists_mock.call_args_list == [call('foo/path/b')]
    assert open_mock.call_args_list == []

def test_get_open_file_fails_to_open_file(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=True)
    open_mock = mocker.patch('builtins.open', side_effect=PermissionError('nope'))
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    with pytest.raises(errors.ContentError, match=r'^Failed to open foo/path/b: nope$'):
        tfs._get_open_file('b')
    assert exists_mock.call_args_list == [call('foo/path/b')]
    assert open_mock.call_args_list == [call('foo/path/b', 'rb')]

def test_get_open_file_opens_file_only_once(mocker):
    exists_mock = mocker.patch('os.path.exists', return_value=True)
    open_mock = mocker.patch('builtins.open', side_effect=('mock file handle1', 'mock file handle2'))
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    for _ in range(5):
        assert tfs._get_open_file('b') == 'mock file handle1'
    assert exists_mock.call_args_list == [call('foo/path/b')]
    assert open_mock.call_args_list == [call('foo/path/b', 'rb')]


def test_get_piece_hash_from_readable_piece(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    get_piece_mock = mocker.patch.object(tfs, 'get_piece', return_value=b'mock piece')
    sha1_mock = mocker.patch('hashlib.sha1', return_value=Mock(digest=Mock(return_value=b'mock hash')))
    assert tfs.get_piece_hash(123) == b'mock hash'
    assert get_piece_mock.call_args_list == [call(123)]
    assert sha1_mock.call_args_list == [call(b'mock piece')]

def test_get_piece_hash_from_unreadable_piece(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    get_piece_mock = mocker.patch.object(tfs, 'get_piece', return_value=None)
    sha1_mock = mocker.patch('hashlib.sha1', return_value=Mock(digest=Mock(return_value=b'mock hash')))
    assert tfs.get_piece_hash(123) is None
    assert get_piece_mock.call_args_list == [call(123)]
    assert sha1_mock.call_args_list == []


def test_torrent_piece_hashes(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    mocker.patch.object(tfs, '_torrent', Mock(metainfo={'info': {'pieces': (
        b'01234567890123456789'
        b'abcdefghijklmnopqrst'
        b'ABCDEFGHIJKLMNOPQRST'
    )}}))
    assert tfs.torrent_piece_hashes == (
        b'01234567890123456789',
        b'abcdefghijklmnopqrst',
        b'ABCDEFGHIJKLMNOPQRST',
    )


def test_verify_piece_gets_valid_piece_index(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    mocker.patch.object(type(tfs), 'torrent_piece_hashes', PropertyMock(
        return_value=(b'foo', b'bar', b'baz'),
    ))
    mocker.patch.object(tfs, 'get_piece_hash', return_value=b'baz')
    assert tfs.verify_piece(0) is False
    assert tfs.verify_piece(1) is False
    assert tfs.verify_piece(2) is True
    with pytest.raises(ValueError, match=r'^piece_index must be in range 0 - 2: 3$'):
        tfs.verify_piece(3)

def test_verify_piece_returns_None_for_nonexisting_files(mocker):
    torrent = Torrent(piece_size=123, files=(File('a', 1), File('b', 2), File('c', 3)))
    tfs = TorrentFileStream(torrent, location='foo/path')
    mocker.patch.object(type(tfs), 'torrent_piece_hashes', PropertyMock(
        return_value=(b'foo', b'bar', b'baz'),
    ))
    mocker.patch.object(tfs, 'get_piece_hash', return_value=None)
    assert tfs.verify_piece(0) is None
    assert tfs.verify_piece(1) is None
    assert tfs.verify_piece(2) is None
    with pytest.raises(ValueError, match=r'^piece_index must be in range 0 - 2: 3$'):
        tfs.verify_piece(3)
