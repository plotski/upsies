class CancelledError(Exception):
    """User cancelled an operation"""
    pass

class ConfigError(Exception):
    """Error while reading from a config file"""
    pass

class DependencyError(Exception):
    """Some external tool is missing (e.g. mediainfo)"""
    pass

class MediainfoError(Exception):
    """Getting mediainfo failed"""
    pass

class NoContentError(Exception):
    """No usable content found (e.g. no video files in the given path)"""
    pass

class ProcessError(Exception):
    """Executing subprocess failed"""
    pass

class PermissionError(Exception):
    """Insufficient permission (e.g. when reading a file)"""
    pass

class RequestError(Exception):
    """Network request failed"""
    pass

class ScreenshotError(Exception):
    """Screenshot creation failed"""
    def __init__(self, msg, video_file, timestamp):
        super().__init__(f'{video_file}: Failed to create screenshot at {timestamp}: {msg}')

class SubprocessError(Exception):
    """
    Exception from a subprocess

    The original traceback from within the subprocess is available as
    :attr:`original_traceback`.
    """
    def __new__(cls, exception, original_traceback):
        self = exception
        self.original_traceback = f'Subprocess traceback:\n{original_traceback.strip()}'
        return self

class TorrentError(Exception):
    """Torrent file creation failed"""
    pass
