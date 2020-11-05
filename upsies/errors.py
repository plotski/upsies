class UpsiesError(Exception):
    """Base class for all exceptions raised by upsies"""

    def __eq__(self, other):
        if isinstance(other, type(self)) and str(other) == str(self):
            print(str(other), repr(other), '==', str(self), repr(self))
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
    pass

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
