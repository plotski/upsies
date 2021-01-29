"""
Abstract base class for scene release databases
"""

import abc

from ... import errors

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SceneDbApiBase(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self):
        """Unique name of the scene release database"""

    @property
    @abc.abstractmethod
    def label(self):
        """User-facing name of the scene release database"""

    async def search(self, *query, group=None, cache=True):
        """
        Search for scene release

        :param query: Search keywords
        :param group: Release group name or `None`

        :return: :class:`list` of release names as :class:`str`
        """
        query = self._normalize_query(query)
        try:
            results = await self._search(query=query, group=group, cache=cache)
        except errors.RequestError as e:
            raise errors.SceneError(e)
        return self._normalize_results(results)

    @abc.abstractmethod
    async def _search(self, query, group=None):
        pass

    def _normalize_query(self, query):
        """Turn sequence of sequences of space-separated words into list of words"""
        return [phrase
                for search_phrases in query
                for phrase in str(search_phrases).split()]

    def _normalize_results(self, results):
        """Return sorted list of sequence of search results"""
        return sorted(results, key=str.casefold)
