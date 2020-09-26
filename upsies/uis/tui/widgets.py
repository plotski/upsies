import collections
import textwrap

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.layout.containers import (HSplit, VSplit, Window,
                                              WindowAlign)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.utils import get_cwidth

from ... import jobs
from . import jobwidgets

import logging  # isort:skip
_log = logging.getLogger(__name__)


hspacer = Window(FormattedTextControl('  '), dont_extend_width=True, dont_extend_height=True)
vspacer = Window(FormattedTextControl(''), dont_extend_width=True, dont_extend_height=True)


def JobWidget(job):
    """
    Factory that returns JobWidgetBase instances based on job type

    :param job: Job instance
    :type job: :class:`JobBase`

    :raise RuntimeError: if `job`'s type is not supported
    """
    if isinstance(job, jobs.search.SearchDbJob):
        return jobwidgets.SearchJobWidget(job)
    elif isinstance(job, jobs.release_name.ReleaseNameJob):
        return jobwidgets.ReleaseNameJobWidget(job)
    elif isinstance(job, jobs.mediainfo.MediainfoJob):
        return jobwidgets.MediainfoJobWidget(job)
    elif isinstance(job, jobs.torrent.CreateTorrentJob):
        return jobwidgets.CreateTorrentJobWidget(job)
    elif isinstance(job, jobs.screenshots.ScreenshotsJob):
        return jobwidgets.ScreenshotsJobWidget(job)
    elif isinstance(job, jobs.submit.SubmissionJobBase):
        return jobwidgets.SubmissionJobWidget(job)
    else:
        raise RuntimeError(f'Unsupported job class: {type(job).__name__}')


class TextField:
    """Single line of non-editable text"""

    def __init__(self, text='', width=None, height=1, extend_width=True, style=''):
        self._text = text
        self._width = width
        self._height = height
        self.container = Window(
            content=FormattedTextControl(lambda: self.text),
            width=width,
            height=height,
            dont_extend_height=True,
            dont_extend_width=not extend_width,
            wrap_lines=True,
            style=' '.join(('class:textfield.info', style)),
        )

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text):
        if isinstance(self._width, int) and self._width > 1:
            width = self._width
            if isinstance(self._height, int):
                height = self._height
            else:
                height = None

            # prompt_toolkit has no support for word wrapping.
            paragraphs = text.split('\n')
            self._text = '\n\n'.join(textwrap.fill(
                paragraph,
                width=width,
                max_lines=height,
                placeholder='…',
            ) for paragraph in paragraphs)
        else:
            self._text = text

    def __pt_container__(self):
        return self.container


class InputField:
    """Single line of user-editable text"""

    def __init__(self, text='', width=None, extend_width=True,
                 on_accepted=None, on_changed=None):
        self.buffer = Buffer(
            multiline=False,
            accept_handler=on_accepted,
            on_text_changed=on_changed
        )
        self.container = Window(
            content=BufferControl(self.buffer),
            width=width,
            dont_extend_height=True,
            dont_extend_width=not extend_width,
            style='class:textfield.input',
        )
        self.set_text(text, ignore_callback=True)

    @property
    def text(self):
        return self.buffer.text

    @text.setter
    def text(self, text):
        self.buffer.set_document(Document(text))

    def set_text(self, text, ignore_callback=False):
        if ignore_callback:
            handlers = self.buffer.on_text_changed._handlers
            self.buffer.on_text_changed._handlers = []
        self.buffer.set_document(Document(text))
        if ignore_callback:
            self.buffer.on_text_changed._handlers = handlers

    def __pt_container__(self):
        return self.container


class HLabel:
    _groups = collections.defaultdict(lambda: [])

    def __init__(self, label, content, group=None):
        label = Window(
            content=FormattedTextControl(text=f'{label} ',
                                         style='class:textfield.label'),
            dont_extend_width=True,
            dont_extend_height=False,
            width=get_cwidth(label) + 1,
            align=WindowAlign.RIGHT,
        )
        self.container = VSplit([label, content])

        self._group = group
        if group is not None:
            self._groups[group].append(label)
            max_width = max(label.width for label in self._groups[group])
            for label in self._groups[group]:
                label.width = max_width

    def __pt_container__(self):
        return self.container


class VLabel:
    def __init__(self, label, content):
        self.container = HSplit([
            Window(FormattedTextControl(text=label, style='class:textfield.label'),
                   dont_extend_height=True),
            content,
        ])

    def __pt_container__(self):
        return self.container


class ProgressBar:
    def __init__(self, text=''):
        self.percent = 0
        self.container = VSplit([
            Window(
                style='class:progressbar class:progressbar.progress',
                width=lambda: Dimension(weight=int(self.percent)),
                height=1,
            ),
            Window(
                style='class:progressbar',
                width=lambda: Dimension(weight=int(100 - self.percent)),
                height=1,
            ),
        ])

    @property
    def percent(self):
        return self._percent

    @percent.setter
    def percent(self, value):
        self._percent = float(value)

    def __pt_container__(self):
        return self.container
