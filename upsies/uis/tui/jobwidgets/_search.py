from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import (ConditionalContainer,
                                              DynamicContainer, HSplit, VSplit,
                                              Window)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.utils import get_cwidth

from ....utils import LazyModule, cache
from .. import widgets
from . import JobWidgetBase

import logging  # isort:skip
_log = logging.getLogger(__name__)

webbrowser = LazyModule(module='webbrowser', namespace=globals())


class SearchDbJobWidget(JobWidgetBase):
    def setup(self):
        right_column_width = 40
        self._widgets = {
            'id' : widgets.TextField(width=15),
            'title' : widgets.InputField(
                on_changed=self.handle_title_changed,
                on_accepted=self.handle_title_selected,
            ),
            'search_results' : _SearchResults(width=50),
            'summary' : widgets.TextField(
                width=right_column_width,
                height=Dimension(min=8),
            ),
            'title_original' : widgets.TextField(
                width=right_column_width,
                height=1,
            ),
            'title_english' : widgets.TextField(
                width=right_column_width,
                height=1,
            ),
            'keywords' : widgets.TextField(
                width=right_column_width,
                height=Dimension(min=1, max=2),
            ),
            'cast' : widgets.TextField(
                width=right_column_width,
                height=Dimension(min=1, max=2),
            ),
            'country' : widgets.TextField(
                width=right_column_width,
                height=Dimension(min=1, max=2),
            ),
        }

        self.job.on_search_results(self.handle_search_results)
        self.job.on_searching_status(self.handle_searching_status)
        self.job.on_info_updated(self.handle_info_updated)

    def handle_title_changed(self, buffer):
        self.job.search(buffer.text)

    def handle_title_selected(self, buffer):
        selected = self._widgets['search_results'].focused_result
        if selected is not None:
            self.job.id_selected(selected.id)
        else:
            self.job.id_selected()

    def handle_searching_status(self, is_searching):
        self._widgets['search_results'].is_searching = is_searching

    def handle_search_results(self, results):
        self._widgets['search_results'].results = results
        get_app().invalidate()

    def handle_info_updated(self, attr, value):
        self._widgets[attr].text = str(value)
        get_app().invalidate()

    @cache.property
    def runtime_widget(self):
        layout = [
            VSplit([
                self._widgets['title'],
                widgets.hspacer,
                widgets.HLabel(
                    label='ID',
                    content=self._widgets['id'],
                ),
            ]),
            widgets.vspacer,
            VSplit([
                widgets.VLabel('Results', self._widgets['search_results']),
                widgets.hspacer,
                HSplit([
                    widgets.VLabel('Summary', self._widgets['summary']),
                    ConditionalContainer(
                        content=widgets.VLabel('Original Title', self._widgets['title_original']),
                        filter=Condition(lambda: self._widgets['title_original'].text),
                    ),
                    ConditionalContainer(
                        content=widgets.VLabel('Also Known As', self._widgets['title_english']),
                        filter=Condition(lambda: self._widgets['title_english'].text),
                    ),
                    ConditionalContainer(
                        content=widgets.VLabel('Keywords', self._widgets['keywords']),
                        filter=Condition(lambda: self._widgets['keywords'].text),
                    ),
                    ConditionalContainer(
                        content=widgets.VLabel('Cast', self._widgets['cast']),
                        filter=Condition(lambda: self._widgets['cast'].text),
                    ),
                    ConditionalContainer(
                        content=widgets.VLabel('Country', self._widgets['country']),
                        filter=Condition(lambda: self._widgets['country'].text),
                    ),
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

        @kb.add('c-o')
        def _(event):
            result = self._widgets['search_results'].focused_result
            webbrowser.open_new_tab(result.url)

        return kb


class _SearchResults(DynamicContainer):
    def __init__(self, results=(), width=40):
        self.results = results
        self._is_searching = False
        self._year_width = 4
        self._type_width = 6
        self._title_width = width - self._year_width - self._type_width - 2
        super().__init__(
            lambda: Window(
                content=FormattedTextControl(self._get_text_fragments, focusable=False),
                width=width,
                style='class:search.result',
            )
        )

    @property
    def is_searching(self):
        return self._is_searching

    @is_searching.setter
    def is_searching(self, value):
        self._is_searching = bool(value)

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

    def _get_text_fragments(self):
        if self._is_searching:
            return [('class:search.result', 'Searching...')]
        elif not self._results:
            return 'No results'

        frags = []
        for i, result in enumerate(self._results):
            title_style = 'class:search.result'

            if i == self._focused_index:
                frags.append(('[SetCursorPosition]', ''))
                title_style += ' class:focused'
                self._focused_result = result

            if get_cwidth(result.title) > self._title_width:
                title = result.title[:self._title_width - 1] + '…'
            else:
                title = result.title
            frags.append((title_style, title.ljust(self._title_width)))

            frags.append(('', (
                ' '
                f'{str(result.year or "").rjust(4)}'
                ' '
                f'{result.type.rjust(6)}'
            )))

            frags.append(('', '\n'))
        frags.pop()  # Remove last newline
        return frags
