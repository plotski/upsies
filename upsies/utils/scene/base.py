"""
Abstract base class for scene release databases
"""

import abc

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SceneDbApiBase(abc.ABC):
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

    def _normalize_query(self, query):
        """Turn sequence of sequences of space-separated words into list of words"""
        return [phrase
                for search_phrases in query
                for phrase in str(search_phrases).split()]

    def _normalize_results(self, results):
        """Return sorted list of sequence of search results"""
        return sorted(results, key=str.casefold)
