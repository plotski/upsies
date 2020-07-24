class ConfigError(Exception):
    pass

class DependencyError(Exception):
    pass

class RequestError(Exception):
    pass

class ProcessError(Exception):
    pass

class PermissionError(Exception):
    pass

class MediainfoError(Exception):
    pass

class NoContentError(Exception):
    pass

class ScreenshotError(Exception):
    def __init__(self, msg, videofile, timestamp):
        super().__init__(f'{videofile}: Failed to create screenshot at {timestamp}: {msg}')

class TorrentError(Exception):
    pass
