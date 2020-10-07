import os
import time

from . import UploaderBase


class Uploader(UploaderBase):
    """Dummy service for testing and debugging"""

    name = 'dummy'

    def _upload(self, image_path):
        time.sleep(0.5)
        url = f'http://localhost/{os.path.basename(image_path)}'
        return {'url': url}
