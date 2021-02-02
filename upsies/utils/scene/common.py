"""
Classes and functions that are used by all :class:`~.base.SceneDbApiBase`
subclasses
"""

from .. import release


class SceneQuery:
    """
    Query for scene release databases

    :param keywords: Search keywords
    :param group: Release group name
    """

    @classmethod
    def from_string(cls, string):
        """
        Create query from :class:`str`

        :param string: Release name or path to release content
        """
        return cls.from_release(release.ReleaseInfo(string))

    @classmethod
    def from_release(cls, release):
        """
        Create query from :class:`dict`-like object

        :param release: :class:`~.release.ReleaseName` or
            :class:`~.release.ReleaseInfo` instance or any :class:`dict`-like
            object with the keys ``title``, ``year``, ``resolution``,
            ``source``, ``video_codec`` and ``group``.
        """
        info = dict(release)
        keywords = [info['title']]
        for key in ('year', 'resolution', 'source', 'video_codec'):
            if info.get(key):
                keywords.append(info[key])
        return cls(*keywords, group=release['group'])

    def __init__(self, *keywords, group=''):
        # Split each keyword
        self._keywords = tuple(k.strip() for kw in keywords
                               for k in str(kw).split()
                               if k.strip())
        self._group = str(group)

    @property
    def keywords(self):
        """Sequence of search terms"""
        return self._keywords

    @property
    def group(self):
        """Release group name"""
        return self._group

    def __repr__(self):
        args = []
        if self.keywords:
            args.append(', '.join((repr(kw) for kw in self.keywords)))
        if self.group:
            args.append(f'group={self.group!r}')
        args_str = ', '.join(args)
        return f'{type(self).__name__}({args_str})'
