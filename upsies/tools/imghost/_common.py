class UploadedImage(str):
    """
    Subclass of `str` that holds arbitrary information from keyword arguments as
    instance attributes

    The instance itself is supposed to be the URL of an uploaded image. Keyword
    arguments can be additional URLs (e.g. thumbnail URL, delete URL) or other
    userful information.
    """

    def __new__(cls, url, **kwargs):
        return super().__new__(cls, url)

    def __init__(self, url, **kwargs):
        self._info = kwargs

    def __getattr__(self, name):
        try:
            return self._info[name]
        except KeyError:
            raise AttributeError(name)

    def __repr__(self):
        kwargs = ', '.join(f'{k}={repr(v)}' for k, v in self._info.items())
        return f'{type(self).__name__}({repr(str(self))}, {kwargs})'
