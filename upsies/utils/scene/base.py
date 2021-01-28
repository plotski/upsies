import abc

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SceneDbBase(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self):
        """Name of the scene release database"""

    @abc.abstractmethod
    async def search(self, *query, group=None):
        """
        Search for scene release

        :param query: Search phrases
        :param group: Release group name or `None`

        :return: :class:`list` of release names as :class:`str`
        """
