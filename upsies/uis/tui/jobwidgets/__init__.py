"""
TUI representation of :class:`jobs <upsies.jobs.base.JobBase>`
"""

from ._base import JobWidgetBase  # isort:skip

from ._config import SetJobWidget
from ._imghost import ImageHostJobWidget
from ._mediainfo import MediainfoJobWidget
from ._prompt import ChoiceJobWidget
from ._release_name import ReleaseNameJobWidget
from ._scene_search import SceneSearchJobWidget
from ._screenshots import ScreenshotsJobWidget
from ._search import SearchWebDbJobWidget
from ._submit import SubmitJobWidget
from ._torrent import (AddTorrentJobWidget, CopyTorrentJobWidget,
                       CreateTorrentJobWidget)
