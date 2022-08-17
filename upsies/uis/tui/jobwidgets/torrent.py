from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import (ConditionalContainer,
                                              HorizontalAlign, HSplit, VSplit,
                                              Window, WindowAlign)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension

from ....utils import cached_property, fs, torrent
from .. import utils, widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class CreateTorrentJobWidget(JobWidgetBase):
    def setup(self):
        self._progress = widgets.ProgressBar()
        self._file_tree = FormattedTextControl()
        self._throughput = FormattedTextControl()
        self._throughput_unit = ''
        self._percent_done = FormattedTextControl()
        self._seconds_elapsed = FormattedTextControl()
        self._seconds_remaining = FormattedTextControl()
        self._seconds_total = FormattedTextControl()
        self._time_started = FormattedTextControl()
        self._time_finished = FormattedTextControl()
        self._current_file_status = ''
        self._current_file_name = FormattedTextControl()

        status_column1 = HSplit(
            children=[
                self.make_readout(' Started:', '_time_started', width=8),
                self.make_readout('Finished:', '_time_finished', width=8),
            ],
        )
        status_column2 = HSplit(
            children=[
                self.make_readout('  Elapsed:', '_seconds_elapsed', width=8),
                self.make_readout('Remaining:', '_seconds_remaining', width=8),
                self.make_readout('    Total:', '_seconds_total', width=8),
            ],
        )
        status_column3 = HSplit(
            children=[
                self.make_readout(
                    lambda: '%'.ljust(len(self._throughput_unit)),
                    '_percent_done',
                    width=6,
                    value_align='right',
                    label_side='right',
                ),
                self.make_readout(
                    lambda: self._throughput_unit.ljust(len(self._throughput_unit)),
                    '_throughput',
                    width=6,
                    value_align='right',
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
                    content=HSplit([
                        status,
                        self.make_readout(
                            lambda: self._current_file_status,
                            '_current_file_name',
                        ),
                        Window(self._file_tree),
                    ]),
                ),
            ],
            style='class:info',
            width=Dimension(min=55, max=100),
        )

        self._activity_indicator = utils.ActivityIndicator(
            callback=self.handle_activity_indicator_state,
            format='Getting announce URL {indicator}'
        )
        self.job.signal.register('announce_url', self.handle_announce_url)
        self.job.signal.register('file_tree', self.handle_file_tree)
        self.job.signal.register('progress_update', self.handle_progress_update)
        self.job.signal.register('finished', lambda _: self.invalidate())

    def make_readout(self, label, attribute, value_align='left', width=None, label_side='left'):
        readout_widget = Window(
            getattr(self, attribute),
            dont_extend_width=True,
            dont_extend_height=True,
            style='class:info.readout',
            width=width,
            align=getattr(WindowAlign, value_align.upper()),
        )
        label_widget = Window(FormattedTextControl(label), dont_extend_width=True)

        if label_side == 'left':
            children = [label_widget, readout_widget]
        elif label_side == 'right':
            children = [readout_widget, label_widget]

        return VSplit(
            children=children,
            padding=1,
            align=HorizontalAlign.CENTER,
        )

    def handle_activity_indicator_state(self, state):
        self.job.info = state
        self.invalidate()

    def handle_file_tree(self, file_tree):
        self._file_tree.text = fs.format_file_tree(file_tree)

    def handle_announce_url(self, announce_url):
        if announce_url is Ellipsis:
            self._activity_indicator.active = True
        else:
            self._activity_indicator.active = False

    def handle_progress_update(self, info):
        self._progress.percent = info.percent_done
        self._percent_done.text = f'{info.percent_done:.2f}'

        self._time_started.text = info.time_started.strftime('%H:%M:%S')
        self._time_finished.text = info.time_finished.strftime('%H:%M:%S')

        def timedelta_string(delta):
            hours, rest = divmod(delta.total_seconds(), 3600)
            minutes, seconds = divmod(rest, 60)
            return f'{hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}'

        self._seconds_elapsed.text = timedelta_string(info.seconds_elapsed)
        self._seconds_remaining.text = timedelta_string(info.seconds_remaining)
        self._seconds_total.text = timedelta_string(info.seconds_total)

        if isinstance(info, torrent.CreateTorrentProgress):
            # Torrent is hashed from fresh files - yummy!
            throughput = info.bytes_per_second.format(
                prefix='binary',
                decimal_places=2,
                trailing_zeros=True,
            )
            self._throughput.text, self._throughput_unit = throughput.split(' ')
            self._throughput_unit += '/s'
            self._current_file_status = 'Hashing'
            self._current_file_name.text = fs.basename(info.filepath)

        elif isinstance(info, torrent.FindTorrentProgress):
            # Torrent hashes are searched for in existing torrents
            if info.exception:
                self.job.warn(info.exception)

            self._throughput.text = f'{info.files_per_second}'
            self._throughput_unit = 'files/s'
            self._current_file_name.text = fs.basename(info.filepath)
            if info.status is False:
                self._current_file_status = 'Cache miss:'
            elif info.status is None:
                self._current_file_status = 'Verifying:'
            elif info.status is True:
                self._current_file_status = 'Cache hit:'

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
