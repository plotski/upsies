import collections
import textwrap

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.key_binding.key_bindings import KeyBindings
from prompt_toolkit.layout.containers import (HSplit, VSplit, Window,
                                              WindowAlign)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.utils import get_cwidth

from . import jobwidgets

import logging  # isort:skip
_log = logging.getLogger(__name__)


hspacer = Window(FormattedTextControl(' '), dont_extend_width=True, dont_extend_height=True)
vspacer = Window(FormattedTextControl(''), dont_extend_width=True, dont_extend_height=True)


def JobWidget(job):
    """
    Factory that returns JobWidgetBase instances based on job type

    The widget class name is created by adding "Widget" to `job`'s class name.
    The widget class is imported from :mod:`.jobwidgets`.

    :param job: Job instance
    :type job: :class:`~.jobs.base.JobBase`

    :raise RuntimeError: if `job`'s type is not supported
    """
    widget_cls_name = type(job).__name__ + 'Widget'
    try:
        widget_cls = getattr(jobwidgets, widget_cls_name)
    except AttributeError:
        raise RuntimeError(f'Unknown widget class: {widget_cls_name}')
    else:
        return widget_cls(job)


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

    def __init__(self, text='', width=None, extend_width=True, read_only=False,
                 on_accepted=None, on_changed=None):
        self.read_only = read_only
        self.on_accepted = on_accepted
        self.buffer = Buffer(
            multiline=False,
            accept_handler=self._accept_handler,
            on_text_changed=on_changed,
            read_only=Condition(lambda: self.read_only),
        )
        self.container = Window(
            content=BufferControl(self.buffer),
            always_hide_cursor=Condition(lambda: self.read_only),
            width=width,
            dont_extend_height=True,
            dont_extend_width=not extend_width,
            style='class:textfield.input',
        )
        if text:
            self.set_text(text, ignore_callback=True)

    def _accept_handler(self, buffer):
        if self.on_accepted:
            self.on_accepted(buffer)
        # Do not clear input field on enter
        return True

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
        self.buffer.set_document(Document(text), bypass_readonly=True)
        if ignore_callback:
            self.buffer.on_text_changed._handlers = handlers

    @property
    def read_only(self):
        return self._read_only

    @read_only.setter
    def read_only(self, read_only):
        self._read_only = bool(read_only)

    def __pt_container__(self):
        return self.container


class RadioList:
    """List of choices the user can select from"""

    def __init__(self, choices, focused=None, on_accepted=None):
        assert len(choices) >= 2
        self.choices = choices
        self.choice = None
        if focused:
            self.focused_index = choices.index(focused)
        else:
            self.focused_index = 0

        kb = KeyBindings()

        @kb.add('up')
        @kb.add('c-p')
        @kb.add('k')
        def _(event):
            self.focused_index = max(0, self.focused_index - 1)

        @kb.add('down')
        @kb.add('c-n')
        @kb.add('j')
        def _(event):
            self.focused_index = min(len(self.choices) - 1, self.focused_index + 1)

        @kb.add('enter')
        @kb.add('c-j')
        @kb.add(' ')
        def _(event):
            if on_accepted is not None:
                on_accepted(self.choices[self.focused_index])

        self.control = FormattedTextControl(
            self._get_text_fragments,
            key_bindings=kb,
            focusable=True,
        )
        self.window = Window(
            content=self.control,
            style='class:textfield.info',
            dont_extend_height=True,
        )

    def _get_text_fragments(self):
        result = []
        width = max(len(value) for value in self.choices)
        for i, value in enumerate(self.choices):
            focused = i == self.focused_index
            if focused:
                style = 'class:radiolist.focus'
                result.append(('[SetCursorPosition]', ''))
                result.append((style, '*'))
            else:
                style = 'class:radiolist'
                result.append((style, ' '))
            result.append((style, ' '))
            result.extend(to_formatted_text(value.ljust(width), style=style))
            result.append(('', '\n'))

        result.pop()  # Remove last newline
        return result

    def __pt_container__(self):
        return self.window


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
