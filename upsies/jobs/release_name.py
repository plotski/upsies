"""
Generate uniform release name
"""

from .. import errors
from ..utils import fs, release
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseNameJob(JobBase):
    """
    Create user-confirmed release name from file or directory path

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``release_name_updating``
            Emitted when :meth:`~.ReleaseName.fetch_info` is called. Registered
            callbacks get no arguments.

        ``release_name_updated``
            Emitted after :meth:`~.ReleaseName.fetch_info` updated the release
            name. Registered callbacks get a :class:`~.release.ReleaseName`
            instance as a positional argument.

        ``release_name``
            Emitted after the user approved a release name. Registered callbacks
            get a :class:`~.release.ReleaseName` instance as a positional
            argument.
    """

    name = 'release-name'
    label = 'Release Name'

    @property
    def cache_id(self):
        """Final segment of `content_path`"""
        return fs.basename(self._content_path)

    @property
    def release_name(self):
        """:class:`~.utils.release.ReleaseName` instance"""
        return self._release_name

    def initialize(self, *, content_path):
        """
        Set internal state

        :param content_path: Path to release file or directory
        """
        self._content_path = content_path
        self._release_name = release.ReleaseName(content_path)
        self.signal.add('release_name_updating')
        self.signal.add('release_name_updated')
        self.signal.add('release_name')

    def release_name_selected(self, release_name):
        """
        :meth:`Send <upsies.jobs.base.JobBase.send>` release name and :meth:`finish
        <upsies.jobs.base.JobBase.finish>`

        This method must be called by the UI when the user accepts the release
        name.

        :param str release_name: Release name as accepted by the user
        """
        # Parse string to get ReleaseName instance for the "release_name" signal
        self._release_name = release.ReleaseName(release_name)
        self.signal.emit('release_name', self.release_name)
        # Send original string as we received it
        self.send(release_name)
        self.finish()

    def fetch_info(self, *args, **kwargs):
        """
        Synchronous wrapper around :meth:`.ReleaseName.fetch_info` that emits
        ``release_name_updating`` before the info is fetched and
        ``release_name_updated`` afterwards.

        All arguments are passed on to :meth:`.ReleaseName.fetch_info`.
        """
        self.signal.emit('release_name_updating')

        def fetch_info_done(_):
            self.signal.emit('release_name_updated', self.release_name)

        self.add_task(
            self._catch_errors(
                self.release_name.fetch_info(*args, **kwargs),
            ),
            callback=fetch_info_done,
        )

    async def _catch_errors(self, coro):
        try:
            return await coro
        except errors.RequestError as e:
            self.error(e)
