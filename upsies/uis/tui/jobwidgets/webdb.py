from prompt_toolkit.application import get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import (DynamicContainer, HSplit, VSplit,
                                              Window)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.utils import get_cwidth

from ....utils import browser, cached_property, webdbs
from .. import utils, widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class WebDbSearchJobWidget(JobWidgetBase):
    def setup(self):
        right_column_width = 40
        self._old_query_text = str(self.job.query)
        self._widgets = {
            'id' : widgets.TextField(width=15, style='class:dialog.search.info'),
            'query' : widgets.InputField(
                style='class:dialog.search.query',
                text=str(self.job.query),
                on_accepted=self.handle_query,
            ),
            'search_results' : _SearchResults(width=40),
            'summary' : widgets.TextField(
                style='class:dialog.search.info',
                width=right_column_width,
                height=8,
            ),
            'title_original' : widgets.TextField(
                style='class:dialog.search.info',
                width=right_column_width,
                height=1,
            ),
            'title_english' : widgets.TextField(
                style='class:dialog.search.info',
                width=right_column_width,
                height=1,
            ),
            'genres' : widgets.TextField(
                style='class:dialog.search.info',
                width=right_column_width,
                height=2,
            ),
            'directors' : widgets.TextField(
                style='class:dialog.search.info',
                width=right_column_width,
                height=1,
            ),
            'cast' : widgets.TextField(
                style='class:dialog.search.info',
                width=right_column_width,
                height=2,
            ),
            'countries' : widgets.TextField(
                style='class:dialog.search.info',
                width=right_column_width,
                height=1,
            ),
        }

        self.job.signal.register('search_results', self.handle_search_results)
        self.job.signal.register('searching_status', self.handle_searching_status)
        self.job.signal.register('info_updating', self.handle_info_updating)
        self.job.signal.register('info_updated', self.handle_info_updated)

    def handle_query(self, buffer):
        query_text = self._widgets['query'].text
        if query_text != self._old_query_text:
            self.job.search(webdbs.Query.from_string(query_text))
            self._widgets['query'].set_text(str(self.job.query))
            self._old_query_text = self._widgets['query'].text
        else:
            # The same query was accepted twice without changing it.
            # Select focused search result.
            selected = self._widgets['search_results'].focused_result
            if selected is not None:
                self.job.result_selected(selected)
            else:
                self.job.result_selected(None)
        self.invalidate()

    def handle_searching_status(self, is_searching):
        self._widgets['search_results'].is_searching = is_searching

    def handle_search_results(self, results):
        self._widgets['search_results'].results = results
        self.invalidate()

    def handle_info_updating(self, attr):
        self._widgets[attr].is_loading = True
        self.invalidate()

    def handle_info_updated(self, attr, value):
        self._widgets[attr].is_loading = False
        self._widgets[attr].text = str(value)
        self.invalidate()

    @cached_property
    def runtime_widget(self):
        w = self._widgets
        layout = [
            VSplit([
                w['query'],
                widgets.hspacer,
                widgets.HLabel(
                    text='ID',
                    content=w['id'],
                    style='class:dialog.search.label',
                ),
            ]),
            widgets.vspacer,
            VSplit([
                HSplit([
                    widgets.VLabel('Results', w['search_results'], style='class:dialog.search.label'),
                    widgets.VLabel('Original Title', w['title_original'], style='class:dialog.search.label'),
                    widgets.VLabel('Also Known As', w['title_english'], style='class:dialog.search.label'),
                ]),
                widgets.hspacer,
                HSplit([
                    widgets.VLabel('Summary', w['summary'], style='class:dialog.search.label'),
                    widgets.VLabel('genres', w['genres'], style='class:dialog.search.label'),
                    widgets.VLabel('Director', w['directors'], style='class:dialog.search.label'),
                    widgets.VLabel('Cast', w['cast'], style='class:dialog.search.label'),
                    widgets.VLabel('Country', w['countries'], style='class:dialog.search.label'),
                ]),
            ]),
            widgets.vspacer,
        ]

        # Wrapping the HSplit in a VSplit limits the width of the first line
        # ("Search" and "... ID" fields) to the width of the search results +
        # summary, etc. This can probably be removed if someone figured out a
        # way to give the search results + summary a dynamic width.
        return VSplit(
            children=[
                HSplit(
                    children=layout,
                    key_bindings=self._make_keybindings(),
                    style='class:dialog.search',
                ),
            ],
        )

    def _make_keybindings(self):
        kb = KeyBindings()

        @kb.add('down')
        @kb.add('c-n')
        @kb.add('tab')
        def _(event):
            prev_result = self._widgets['search_results'].focused_result
            self._widgets['search_results'].focus_next()
            if prev_result != self._widgets['search_results'].focused_result:
                self.job.result_focused(self._widgets['search_results'].focused_result)

        @kb.add('up')
        @kb.add('c-p')
        @kb.add('s-tab')
        def _(event):
            prev_result = self._widgets['search_results'].focused_result
            self._widgets['search_results'].select_previous()
            if prev_result != self._widgets['search_results'].focused_result:
                self.job.result_focused(self._widgets['search_results'].focused_result)

        # Alt-Enter
        @kb.add('escape', 'enter')
        def _(event):
            url = self._widgets['search_results'].focused_result.url
            browser.open(url)

        return kb


class _SearchResults(DynamicContainer):
    def __init__(self, results=(), width=40):
        self.results = results
        self._year_width = 4
        self._type_width = 6
        self._title_width = width - self._year_width - self._type_width - 2
        self._throbber = utils.Throbber(callback=self._throbber_callback)
        self._throbber_string = '...'
        super().__init__(
            lambda: Window(
                content=FormattedTextControl(self._get_text_fragments, focusable=False),
                width=width,
                height=14,
                style='class:dialog.search.results',
            )
        )

    @property
    def is_searching(self):
        return self._throbber.active

    @is_searching.setter
    def is_searching(self, value):
        self._throbber.active = bool(value)

    @property
    def results(self):
        return self._results

    @results.setter
    def results(self, results):
        self._results = tuple(results)
        self._focused_index = 0

    @property
    def focused_result(self):
        if self._results:
            return self._results[self._focused_index]
        else:
            return None

    def focus_next(self):
        if self._focused_index < len(self._results) - 1:
            self._focused_index += 1

    def select_previous(self):
        if self._focused_index > 0:
            self._focused_index -= 1

    def select_first(self):
        self._focused_index = 0

    def select_last(self):
        self._focused_index = len(self._results) - 1

    def _throbber_callback(self, string):
        self._throbber_string = string
        get_app().invalidate()

    def _get_text_fragments(self):
        if self.is_searching:
            return [('class:dialog.search.results', self._throbber_string)]
        elif not self._results:
            return 'No results'

        frags = []
        for i, result in enumerate(self._results):
            if i == self._focused_index:
                title_style = 'class:dialog.search.results.focused'
                frags.append(('[SetCursorPosition]', ''))
                self._focused_result = result
            else:
                title_style = 'class:dialog.search.results'

            if get_cwidth(result.title) > self._title_width:
                title = result.title[:self._title_width - 1] + '…'
            else:
                title = result.title
            frags.append((title_style, title.ljust(self._title_width)))

            frags.append(('', (
                ' '
                f'{str(result.year or "").rjust(4)}'
                ' '
                f'{str(result.type).rjust(6)}'
            )))

            frags.append(('', '\n'))
        frags.pop()  # Remove last newline
        return frags
