"""
Anything implementation-independent
"""

class UploadedImage(str):
    """
    Subclass of :class:`str` that holds information from keyword arguments as
    instance attributes

    The instance itself is supposed to be the URL of an uploaded image.
    """

    def __new__(cls, url, thumbnail_url=None, delete_url=None, edit_url=None):
        self = super().__new__(cls, url)
        self._thumbnail_url = thumbnail_url
        self._delete_url = delete_url
        self._edit_url = edit_url
        return self

    @property
    def thumbnail_url(self):
        return self._thumbnail_url

    @property
    def delete_url(self):
        return self._delete_url

    @property
    def edit_url(self):
        return self._edit_url

    def __repr__(self):
        kwargs = []
        for name in ('thumbnail_url', 'delete_url', 'edit_url'):
            value = getattr(self, name)
            if value:
                kwargs.append(f'{name}={repr(value)}')
        if kwargs:
            return f'{type(self).__name__}({repr(str(self))}, {", ".join(kwargs)})'
        else:
            return f'{type(self).__name__}({repr(str(self))})'
