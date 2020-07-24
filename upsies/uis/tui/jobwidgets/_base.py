import abc

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import (ConditionalContainer, HSplit,
                                              Window)
from prompt_toolkit.layout.controls import FormattedTextControl

from .. import widgets

import logging  # isort:skip
_log = logging.getLogger(__name__)


class JobWidgetBase(abc.ABC):
    def __init__(self, job):
        self.job = job
        self.setup()
        self._main_widget = HSplit(
            style='class:output',
            children=[
                # Status / Progress
                ConditionalContainer(
                    filter=Condition(lambda: not self.job.is_finished),
                    content=self.runtime_widget,
                ),
                # Final output
                ConditionalContainer(
                    filter=Condition(lambda: self.job.is_finished and self.job.output),
                    content=self.output_widget,
                ),
                # More info that isn't part of the final output
                ConditionalContainer(
                    filter=Condition(lambda: bool(self.job.info)),
                    content=self.info_widget,
                ),
                # Errors
                ConditionalContainer(
                    filter=Condition(lambda: bool(self.job.errors)),
                    content=self.errors_widget,
                ),
            ],
        )
        self._container = widgets.HLabel(
            group='jobs',
            label=self.job.label,
            content=self._main_widget,
        )

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
            style='class:result,info',
            content=FormattedTextControl(lambda: str(self.job.info)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def output_widget(self):
        return Window(
            style='class:result',
            content=FormattedTextControl(lambda: '\n'.join(self.job.output)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    @property
    def errors_widget(self):
        return Window(
            style='class:error',
            content=FormattedTextControl(lambda: '\n'.join(str(e) for e in self.job.errors)),
            dont_extend_height=True,
            wrap_lines=True,
        )

    def __pt_container__(self):
        return self._container
