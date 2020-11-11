class UpsiesError(Exception):
    """Base class for all exceptions raised by upsies"""

    def __eq__(self, other):
        if isinstance(other, type(self)) and str(other) == str(self):
            return True
        else:
            return NotImplemented

class CancelledError(UpsiesError):
    """User cancelled an operation"""
    pass

class ConfigError(UpsiesError):
    """Error while reading from a config file"""
    pass

class DependencyError(UpsiesError):
    """Some external tool is missing (e.g. mediainfo)"""
    pass

class MediainfoError(UpsiesError):
    """Getting mediainfo failed"""
    pass

class ContentError(UpsiesError):
    """
    Something is wrong with the user-provided content, e.g. no video files in
    the given directory or no permission to read
    """
    pass

class ProcessError(UpsiesError):
    """Executing subprocess failed"""
    pass

class RequestError(UpsiesError):
    """Network request failed"""
    def __init__(self, msg, headers={}, status_code=None):
        super().__init__(msg)
        self._headers = headers
        self._status_code = status_code

    @property
    def headers(self):
        """HTTP headers from server response or empty `dict`"""
        return self._headers

    @property
    def status_code(self):
        """HTTP status code (e.g. 404) or `None`"""
        return self._status_code


class ScreenshotError(UpsiesError):
    """Screenshot creation failed"""
    def __init__(self, msg, video_file=None, timestamp=None):
        if not video_file or not timestamp:
            super().__init__(msg)
        else:
            super().__init__(f'{video_file}: Failed to create screenshot at {timestamp}: {msg}')

class TorrentError(UpsiesError):
    """Torrent file creation failed"""
    pass

def SubprocessError(exception, original_traceback):
    """Attach `original_traceback` to `exception`"""
    exception.original_traceback = f'Subprocess traceback:\n{original_traceback.strip()}'
    return exception
