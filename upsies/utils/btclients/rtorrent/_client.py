import asyncio
import http
import os
import urllib
import xmlrpc

from .... import errors, utils
from ..base import ClientApiBase
from . import _scgi

import logging  # isort:skip
_log = logging.getLogger(__name__)


class RtorrentClientApi(ClientApiBase):
    """
    rtorrent API

    References:
        https://github.com/rakshasa/rtorrent/wiki/RPC-Setup-XMLRPC
        https://docs.python.org/3/library/xmlrpc.client.html
    """

    name = 'rtorrent'

    default_config = {
        'url': 'http://localhost:5000/',
        'check_after_add': utils.types.Bool('no'),
    }

    add_torrent_timeout = 10
    add_torrent_check_delay = 0.5

    @utils.cached_property
    def _proxy(self):
        if not self.config['url']:
            raise errors.RequestError('No URL provided')

        parts = urllib.parse.urlsplit(self.config['url'])
        if parts.scheme == 'scgi':
            if parts.netloc and ':' in parts.netloc:
                # If there is a port in netloc, it's a host.
                kwargs = {
                    'uri': 'http://' + parts.netloc,
                    'transport': _scgi.ScgiTransport(),
                }
            else:
                # If there is no port in the host, it's the first segment of a
                # relative path. For absolute paths, netloc is empty.
                socket_path = parts.netloc + parts.path
                kwargs = {
                    'uri': 'http://1',
                    'transport': _scgi.ScgiTransport(socket_path=socket_path),
                }
        else:
            kwargs = {
                'uri': self.config['url'],
            }
        print(kwargs)
        _log.debug('Creating XMLRPC Proxy: %r', kwargs)
        return xmlrpc.client.ServerProxy(**kwargs)

    def _request(self, method, *args):
        attr = self._proxy
        for name in method.split('.'):
            attr = getattr(attr, name)

        try:
            return attr(*args)
        except http.client.HTTPException as e:
            raise errors.RequestError(e)
        except OSError as e:
            msg = e.strerror if e.strerror else str(e)
            raise errors.RequestError(msg)

    def _get_torrent_hashes(self):
        return tuple(infohash.lower() for infohash in self._request('download_list'))

    async def add_torrent(self, torrent_path, download_path=None):
        _log.info('Adding to rtorrent: %r', torrent_path)
        torrent_path = str(os.path.abspath(torrent_path))
        if download_path:
            download_path = str(os.path.abspath(download_path))

        try:
            args = ['', self._get_torrent_data(torrent_path, download_path)]
        except errors.TorrentError as e:
            raise errors.RequestError(e)

        if download_path:
            args.append('d.directory.set="'
                        + download_path.replace('"', r'\"')
                        + '"')

        self._request('load.raw_start_verbose', *args)
        try:
            infohash = self.read_torrent(torrent_path).infohash
        except errors.TorrentError as e:
            raise errors.RequestError(e)

        aioloop = asyncio.get_event_loop()
        start_time = aioloop.time()
        while aioloop.time() - start_time < self.add_torrent_timeout:
            infohashes = self._get_torrent_hashes()
            if infohash in infohashes:
                return infohash
            else:
                await asyncio.sleep(self.add_torrent_check_delay)
        raise errors.RequestError('Unknown error')

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
        filestream = utils.torrent.TorrentFileStream(torrent, download_path)

        files = []
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
