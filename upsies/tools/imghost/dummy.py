from . import UploaderBase


class Uploader(UploaderBase):
    """Dummy service for testing and debugging"""

    name = 'dummy'

    def _upload(self, image_path):
        import time, os
        time.sleep(0.5)
        url = f'http://localhost/{os.path.basename(image_path)}'
        return {'url': url}
