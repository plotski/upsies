from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import (ConditionalContainer,
                                              HorizontalAlign, HSplit, VSplit,
                                              Window, WindowAlign)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension

from ....utils import cached_property, fs
from .. import utils, widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._progress = widgets.ProgressBar()
        self._file_tree = FormattedTextControl()
        self._bytes_per_second = FormattedTextControl()
        self._percent_done = FormattedTextControl()
        self._seconds_elapsed = FormattedTextControl()
        self._seconds_remaining = FormattedTextControl()
        self._seconds_total = FormattedTextControl()
        self._time_started = FormattedTextControl()
        self._time_finished = FormattedTextControl()

        status_column1 = HSplit(
            children=[
                self.make_readout(' Started:', '_time_started', align='left', width=8),
                self.make_readout('Finished:', '_time_finished', align='left', width=8),
            ],
        )
        status_column2 = HSplit(
            children=[
                self.make_readout('  Elapsed:', '_seconds_elapsed', align='center', width=8),
                self.make_readout('Remaining:', '_seconds_remaining', align='center', width=8),
                self.make_readout('    Total:', '_seconds_total', align='center', width=8),
            ],
        )
        status_column3 = HSplit(
            children=[
                self.make_readout('%'.ljust(5), '_percent_done', align='right', width=6, label_side='right'),
                self.make_readout(
                    lambda: (self._bytes_per_second_string.split(' ')[1] + '/s').ljust(5),
                    '_bytes_per_second',
                    align='right',
                    width=6,
                    label_side='right',
                ),
            ],
        )
        status = VSplit(children=[status_column1, status_column2, status_column3], padding=3)

        self._runtime_widget = HSplit(
            children=[
                self._progress,
                ConditionalContainer(
                    filter=Condition(lambda: self._progress.percent > 0),
                    content=HSplit([status, Window(self._file_tree)]),
                ),
            ],
            style='class:info',
            width=Dimension(min=55, max=100),
        )

        self._throbber = utils.Throbber(
            callback=self.handle_throbber_state,
            format='Getting announce URL {throbber}'
        )
        self.job.signal.register('announce_url', self.handle_announce_url)
        self.job.signal.register('file_tree', self.handle_file_tree)
        self.job.signal.register('progress_update', self.handle_progress_update)
        self.job.signal.register('finished', lambda _: self.invalidate())

    def make_readout(self, label, attribute, align, width, label_side='left'):
        readout_widget = Window(
            getattr(self, attribute),
            dont_extend_width=True,
            dont_extend_height=True,
            style='class:info.readout',
            width=width,
            align=WindowAlign.RIGHT,
        )
        label_widget = Window(FormattedTextControl(label), dont_extend_width=True)

        if label_side == 'left':
            children = [label_widget, readout_widget]
        elif label_side == 'right':
            children = [readout_widget, label_widget]

        return VSplit(
            children=children,
            padding=1,
            align=getattr(HorizontalAlign, align.upper()),
        )

    def handle_throbber_state(self, state):
        self.job.info = state
        self.invalidate()

    def handle_file_tree(self, file_tree):
        self._file_tree.text = fs.format_file_tree(file_tree)

    def handle_announce_url(self, announce_url):
        if announce_url is Ellipsis:
            self._throbber.active = True
        else:
            self._throbber.active = False

    def handle_progress_update(self, status):
        self._progress.percent = status.percent_done

        self._bytes_per_second_string = status.bytes_per_second.format(
            prefix='binary',
            decimal_places=2,
            trailing_zeros=True,
        )
        self._bytes_per_second.text = self._bytes_per_second_string.split(' ')[0]

        self._percent_done.text = f'{status.percent_done:.2f}'

        self._time_started.text = status.time_started.strftime('%H:%M:%S')
        self._time_finished.text = status.time_finished.strftime('%H:%M:%S')

        def timedelta_string(delta):
            hours, rest = divmod(delta.total_seconds(), 3600)
            minutes, seconds = divmod(rest, 60)
            return f'{hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}'

        self._seconds_elapsed.text = timedelta_string(status.seconds_elapsed)
        self._seconds_remaining.text = timedelta_string(status.seconds_remaining)
        self._seconds_total.text = timedelta_string(status.seconds_total)

        self.invalidate()

    @cached_property
    def runtime_widget(self):
        return self._runtime_widget


class AddTorrentJobWidget(JobWidgetBase):
    def setup(self):
        pass

    @cached_property
    def runtime_widget(self):
        return None


class CopyTorrentJobWidget(JobWidgetBase):
    def setup(self):
        pass

    @cached_property
    def runtime_widget(self):
        return None
