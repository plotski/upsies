"""
Generate uniform release name
"""

import asyncio

from ..utils import release
from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ReleaseNameJob(JobBase):
    """
    Create user-confirmed release name from file or directory path

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``release_name_updated``
            Emitted after :meth:`~.ReleaseName.fetch_info` updated the release
            name. Registered callbacks get a :class:`~.release.ReleaseName`
            instance as a positional argument.

        ``release_name``
            Emitted after the user approved a release name. Registered callbacks
            get a :class:`~.release.ReleaseName` instance as a positional
            argument.

            .. note:: This signal is handy because the ``output`` signal always
                      emits a string so it can be cached in a user-readable text
                      file.
    """

    name = 'release-name'
    label = 'Release Name'

    @property
    def release_name(self):
        """:class:`~.utils.release.ReleaseName` instance"""
        return self._release_name

    def initialize(self, *, content_path):
        """
        Set internal state

        :param content_path: Path to release file or directory
        """
        self._release_name = release.ReleaseName(content_path)
        self.signal.add('release_name_updated')
        self.signal.add('release_name')

    def release_name_selected(self, release_name):
        """
        :meth:`Send <upsies.jobs.base.JobBase.send>` release name and :meth:`finish
        <upsies.jobs.base.JobBase.finish>`

        This method must be called by the UI when the user accepts the release
        name.

        :param ReleaseName release_name: Release name as accepted by the user
        """
        assert isinstance(release_name, release.ReleaseName)
        self._release_name = release_name
        self.signal.emit('release_name', self.release_name)
        self.send(str(self.release_name))
        self.finish()

    def fetch_info(self, *args, **kwargs):
        """
        Synchronous wrapper around :meth:`.ReleaseName.fetch_info` that emits the
        ``release_name_updated`` signal

        All arguments are passed on to :meth:`.ReleaseName.fetch_info`.
        """
        task = asyncio.ensure_future(
            self.release_name.fetch_info(*args, **kwargs),
        )

        def fetch_info_done(task):
            exc = task.exception()
            if exc:
                self.exception(exc)
            else:
                self.signal.emit('release_name_updated', self.release_name)

        task.add_done_callback(fetch_info_done)
