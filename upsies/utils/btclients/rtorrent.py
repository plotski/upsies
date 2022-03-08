import asyncio
import os

import aiobtclientrpc

from ... import errors, utils
from .base import ClientApiBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class RtorrentClientApi(ClientApiBase):
    """
    rtorrent API

    References:
        https://github.com/rakshasa/rtorrent/wiki/rTorrent-0.9-Comprehensive-Command-list-(WIP)
        https://docs.python.org/3/library/xmlrpc.client.html
        https://github.com/rakshasa/rtorrent/wiki/RPC-Setup-XMLRPC
    """

    name = 'rtorrent'
    label = 'rTorrent'

    default_config = {
        'url': utils.configfiles.config_value(
            value='scgi://localhost:5000',
            description=(
                'Formats:\n'
                '  [https|http]://<username>:<password>@<host>:<port>\n'
                '  [https|http]://<host>:<port>\n'
                '  scgi://<host>:<port>\n'
                '  scgi:///path/to/rtorrent/rpc.socket'
            ),
        ),
        'username': '',
        'password': '',
        'check_after_add': utils.configfiles.config_value(
            value=utils.types.Bool('no'),
            description=f'Whether to tell {label} to verify pieces after adding the torrent.',
        ),
    }

    @utils.cached_property
    def _rpc(self):
        return aiobtclientrpc.RtorrentRPC(
            url=self.config['url'],
            username=self.config['username'] or None,
            password=self.config['password'] or None,
        )

    async def add_torrent(self, torrent_path, download_path=None):
        _log.info('Adding to rtorrent: %r', torrent_path)

        torrent_path = str(os.path.abspath(torrent_path))
        if download_path:
            download_path = str(os.path.abspath(download_path))

        # Read torrent file
        try:
            args = ['', self._get_torrent_data(torrent_path, download_path)]
            infohash = self.read_torrent(torrent_path).infohash
        except errors.TorrentError as e:
            raise errors.RequestError(e)

        if download_path:
            args.append('d.directory.set="'
                        + download_path.replace('"', r'\"')
                        + '"')

        # Add torrent
        try:
            async with self._rpc:
                await self._rpc.call(await self._get_load_command(), *args)
                await self._wait_for_added_torrent(infohash)
                return infohash
        except aiobtclientrpc.Error as e:
            raise errors.RequestError(e)

    _add_torrent_timeout = 10
    _add_torrent_check_delay = 0.5

    async def _wait_for_added_torrent(self, infohash):
        aioloop = asyncio.get_event_loop()
        start_time = aioloop.time()
        while aioloop.time() - start_time < self._add_torrent_timeout:
            infohashes = await self._get_torrent_hashes()
            if infohash in infohashes:
                return
            else:
                await asyncio.sleep(self._add_torrent_check_delay)
        raise errors.RequestError('Unknown error')

    async def _get_load_command(self):
        available_commands = await self._rpc.call('system.listMethods')
        wanted_commands = (
            'load.raw_start_verbose',
            'load.raw_start',
        )
        for cmd in wanted_commands:
            if cmd in available_commands:
                return cmd
        raise RuntimeError('Failed to find load command')

    def _get_torrent_data(self, torrent_path, download_path=None):
        if download_path and not self.config['check_after_add']:
            try:
                torrent = self._get_torrent_data_with_resume_fields(torrent_path, download_path)
            except errors.TorrentError as e:
                _log.debug('Failed to generate libtorrent_resume fields: %r', e)
                torrent = self.read_torrent(torrent_path)
        else:
            torrent = self.read_torrent(torrent_path)
        return torrent.dump()

    def _get_torrent_data_with_resume_fields(self, torrent_path, download_path):
        _log.debug('Adding libtorrent_resume fields')
        torrent = self.read_torrent(torrent_path)
        files = []
        with utils.torrent.TorrentFileStream(torrent, download_path) as filestream:
            for file in torrent.files:
                filepath = os.path.join(download_path, file)
                files.append({
                    'mtime': self._get_mtime(filepath),
                    # Number of chunks in this file
                    'completed': len(filestream.get_piece_indexes_for_file(file)),
                    # rtorrent_fast_resume.pl sets priority to 0 while autotorrent
                    # sets it to 1. Not sure what's better or if this matters at
                    # all.
                    'priority': 0,
                })

        piece_count = len(torrent.metainfo['info']['pieces']) // 20
        torrent.metainfo['libtorrent_resume'] = {
            'files': files,
            'bitfield': piece_count,
        }
        return torrent

    def _get_mtime(self, path):
        try:
            return int(os.stat(path).st_mtime)
        except OSError as e:
            msg = e.strerror if e.strerror else str(e)
            raise errors.TorrentError(msg)

    async def _get_torrent_hashes(self):
        infohashes = await self._rpc.call('download_list')
        return tuple(infohash.lower() for infohash in infohashes)
