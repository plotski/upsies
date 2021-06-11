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
    """User-interaction and information display for :class:`~.jobs.JobBase` instance"""

    _no_runtime_widget = Window(
        dont_extend_height=True,
        style='class:info',
    )

    def __init__(self, job, app):
        self._job = job
        self._app = app
        self.setup()
        self.job.signal.register('info', lambda _: self.invalidate())
        self.job.signal.register('warning', lambda _: self.invalidate())
        main_widget = HSplit(
            children=[
                # Status information or user interaction
                ConditionalContainer(
                    filter=Condition(lambda: not self.job.is_finished),
                    content=self.runtime_widget or self._no_runtime_widget,
                ),
                # Result
                ConditionalContainer(
                    filter=Condition(lambda: self.job.output),
                    content=self.output_widget,
                ),
                # Additional info that isn't part of the job's main result
                # (e.g. CreateTorrentJobWidget can show the files in the
                # torrent, but the output is the torrent file path.)
                ConditionalContainer(
                    filter=Condition(lambda: not self.job.is_finished and bool(self.job.info)),
                    content=self.info_widget,
                ),
                # Warnings
                ConditionalContainer(
                    filter=Condition(lambda: bool(self.job.warnings)),
                    content=self.warnings_widget,
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
            text=self.job.label,
            style='class:label',
            content=main_widget,
        )
        self._container = ConditionalContainer(
            filter=Condition(lambda: self.job.errors or not self.job.hidden),
            content=label,
        )

    @property
    def job(self):
        """Underlying :class:`~.JobBase` instance"""
        return self._job

    @abc.abstractmethod
    def setup(self):
        """
        Called on object creation

        Create widgets and register :attr:`job` callbacks.
        """

    @property
    @abc.abstractmethod
    def runtime_widget(self):
        """
        Interactive or status that is displayed while this job is running

        :return: :class:`~.prompt_toolkit.layout.containers.Window` object or
            `None`
        """

    @property
    def output_widget(self):
        """
        Job :attr:`~.JobBase.output`

        :return: :class:`~.prompt_toolkit.layout.containers.Window` object
        """
        return Window(
            style='class:output',
            # FIXME: If output is empty, prompt-toolkit ignores the
            #        "dont_extend_height" argument. Using a space (0x20) as a
            #        placeholder seems to prevent this issue.
            content=FormattedTextControl(lambda: '\n'.join(self.job.output) or ' '),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def info_widget(self):
        """
        :attr:`~.JobBase.info` that is only displayed while this job is running

        :return: :class:`~.prompt_toolkit.layout.containers.Window` object
        """
        return Window(
            style='class:info',
            content=FormattedTextControl(lambda: str(self.job.info)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def warnings_widget(self):
        """
        Any :attr:`~.JobBase.warnings`

        :return: :class:`~.prompt_toolkit.layout.containers.Window` object
        """
        return Window(
            style='class:warning',
            content=FormattedTextControl(lambda: '\n'.join(str(e) for e in self.job.warnings)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def errors_widget(self):
        """
        Any :attr:`~.JobBase.errors`

        :return: :class:`~.prompt_toolkit.layout.containers.Window` object
        """
        return Window(
            style='class:error',
            content=FormattedTextControl(lambda: '\n'.join(str(e) for e in self.job.errors)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def is_interactive(self):
        """Whether this job needs user interaction"""
        if self.runtime_widget:
            for c in walk(to_container(self.runtime_widget), skip_hidden=True):
                if isinstance(c, Window) and c.content.is_focusable():
                    return True
        return False

    def invalidate(self):
        """Schedule redrawing of the TUI"""
        self._app.invalidate()

    def __pt_container__(self):
        return self._container
