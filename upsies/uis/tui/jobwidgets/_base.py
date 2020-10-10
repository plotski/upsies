import abc

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import (ConditionalContainer, HSplit,
                                              Window, to_container)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import walk

from .. import widgets

import logging  # isort:skip
_log = logging.getLogger(__name__)


class JobWidgetBase(abc.ABC):
    """User-interaction and information display for :class:`JobBase` instance"""

    def __init__(self, job):
        self._job = job
        self.setup()
        main_widget = HSplit(
            children=[
                # Status or progress information
                ConditionalContainer(
                    filter=Condition(lambda: not self.job.is_finished),
                    content=self.runtime_widget,
                ),
                # Additional info that isn't part of the job's main result
                # (e.g. CreateTorrentJobWidget can show the files in the
                # torrent, but the output is the torrent file path.)
                ConditionalContainer(
                    filter=Condition(lambda: bool(self.job.info)),
                    content=self.info_widget,
                ),
                # Final output
                ConditionalContainer(
                    filter=Condition(lambda: self.job.output),
                    content=self.output_widget,
                ),
                # Errors
                ConditionalContainer(
                    filter=Condition(lambda: bool(self.job.errors)),
                    content=self.errors_widget,
                ),
            ],
        )
        label = widgets.HLabel(
            group='jobs',
            label=self.job.label,
            content=main_widget,
        )
        self._container = ConditionalContainer(
            filter=Condition(lambda: self.job.errors or not self.job.quiet),
            content=label,
        )

    @property
    def job(self):
        """Underlying :class:`JobBase` instance"""
        return self._job

    @abc.abstractmethod
    def setup(self):
        pass

    @abc.abstractmethod
    def activate(self):
        pass

    @property
    @abc.abstractmethod
    def runtime_widget(self):
        pass

    @property
    def info_widget(self):
        return Window(
            style='class:job.info',
            content=FormattedTextControl(lambda: str(self.job.info)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def output_widget(self):
        return Window(
            style='class:job.output',
            content=FormattedTextControl(lambda: '\n'.join(self.job.output)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def errors_widget(self):
        return Window(
            style='class:job.error',
            content=FormattedTextControl(lambda: '\n'.join(str(e) for e in self.job.errors)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def is_interactive(self):
        """Whether this job needs user interaction"""
        for c in walk(to_container(self.runtime_widget), skip_hidden=True):
            if isinstance(c, Window) and c.content.is_focusable():
                return True
        return False

    def __pt_container__(self):
        return self._container
