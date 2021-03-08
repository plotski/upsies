"""
Get information from the user
"""

import collections

from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ChoiceJob(JobBase):
    """
    Ask the user to choose from a set of values

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``dialog_updated``
            Emitted when the :attr:`choices` or :attr:`focused` properties are
            set. Registered callbacks get the job instance as a positional
            argument.

        ``chosen``
            Emitted when the :attr:`choice` property is set. Registered
            callbacks get the job instance as a positional argument.
    """

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

    @property
    def cache_id(self):
        """:attr:`name` and :attr:`text`"""
        if self.is_finished:
            return (self.name, self.choice)

    @property
    def choices(self):
        """
        Sequence of choices the user can make

        A choice is a :class:`tuple` with 2 items. The first item is a
        human-readable :class:`str` and the second item is any object that is
        emitted via the ``chosen`` signal and made available as :attr:`choice`
        when the job is finished.

        Choices may also be passed as a flat iterable of :class:`str`, in which
        case both items in the tuple are identical.

        When setting this property, focus is preserved if the focused choice
        exists in the new sequence of choices. Otherwise, the first choice is
        focused.
        """
        return getattr(self, '_choices', ())

    @choices.setter
    def choices(self, choices):
        valid_choices = []
        for choice in choices:
            if isinstance(choice, str):
                valid_choices.append((choice, choice))
            elif isinstance(choice, collections.abc.Sequence):
                if len(choice) != 2:
                    raise ValueError(f'Choice must be 2-tuple, not {choice!r}')
                else:
                    valid_choices.append((str(choice[0]), choice[1]))
            else:
                raise ValueError(f'Choice must be 2-tuple, not {choice!r}')

        if len(valid_choices) < 2:
            raise ValueError(f'There must be at least 2 choices: {choices!r}')

        prev_focused = self.focused
        self._choices = tuple(valid_choices)
        if prev_focused in valid_choices:
            self._focused_index = valid_choices.index(prev_focused)
        else:
            self._focused_index = 0

        self.signal.emit('dialog_updated', self)

    @property
    def focused(self):
        """
        Currently focused choice (2-tuple)

        Setting this property to `None` focuses the first choice in
        :attr:`choices`.

        Setting this property to an :class:`int` focuses the choice at that
        index in :attr:`choices`.

        Setting this property to any other value assumes that value is a choice
        in :attr:`choices` or one of the values of one of the :attr:`choices`.
        If that fails, :class:`ValueError` is raised.
        """
        focused_index = getattr(self, '_focused_index', None)
        if focused_index is not None:
            return self.choices[focused_index]

    @focused.setter
    def focused(self, focused):
        if focused is None:
            self._focused_index = 0
        elif isinstance(focused, int):
            index = max(0, min(focused, len(self.choices) - 1))
            self._focused_index = index
        elif focused in self.choices:
            self._focused_index = self.choices.index(focused)
        else:
            for i, choice in enumerate(self.choices):
                if focused == choice[0] or focused == choice[1]:
                    self._focused_index = i
                    break
            # The else clause is evaluated if the for loop ends without reaching
            # `break`.
            else:
                raise ValueError(f'Invalid choice: {focused!r}')

        self.signal.emit('dialog_updated', self)

    @property
    def focused_index(self):
        """Index of currently focused choice in :attr:`choices`"""
        return getattr(self, '_focused_index', None)

    @property
    def choice(self):
        """
        User-chosen value if job is finished, `None` otherwise

        Setting this property finishes the job.

        While :attr:`output` contains the user-readable string (first item of
        the chosen item in :attr:`choices`), this is the object attached to it
        (second item).

        This property can be set to an index in :attr:`choices`, an item in
        :attr:`choices` or the first or second item of an item in
        :attr:`choices`.
        """
        if self.is_finished:
            return getattr(self, '_choice', None)

    @choice.setter
    def choice(self, choice):
        def choose(choice):
            # Machine-readable choice
            self._choice = choice[1]
            self.signal.emit('chosen', self)
            # User-readable string
            self.send(choice[0])
            self.finish()

        if choice in self.choices:
            choose(choice)
        elif isinstance(choice, int):
            try:
                choose(self.choices[choice])
            except IndexError:
                raise ValueError(f'Invalid choice: {choice!r}')
        elif isinstance(choice, str):
            for c in self.choices:
                if choice == c[0] or choice == c[1]:
                    choose(c)
                    break
            else:
                raise ValueError(f'Invalid choice: {choice!r}')
        else:
            raise ValueError(f'Invalid choice: {choice!r}')

    def initialize(self, *, name, label, choices, focused=None):
        """
        Set internal state

        :param name: Name for internal use
        :param label: Name for user-facing use
        :param choices: Iterable of choices the user can make
        :param focused: See :attr:`focused`

        :raise ValueError: if `choices` is shorter than 2 or `focused` is
            invalid
        """
        self._name = str(name)
        self._label = str(label)
        self.signal.add('dialog_updated')
        self.signal.add('chosen')
        self.choices = choices
        self.focused = focused


class TextFieldJob(JobBase):
    """
    Ask the user for text input

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``dialog_updated``
            Emitted when any property is set. Registered callbacks get the job
            instance as a positional argument.

        ``accepted``
            Emitted when the user accepts the text. Registered callbacks get the
            entered text as a positional argument.
    """

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

    @property
    def cache_id(self):
        """:attr:`name` and :attr:`text`"""
        return (self.name, self.text)

    @property
    def text(self):
        """
        Current text

        Setting this property calls `validator` and raises any exception from
        that.
        """
        return getattr(self, '_text', ())

    @text.setter
    def text(self, text):
        self._text = str(text)
        self.signal.emit('dialog_updated', self)

    @property
    def obscured(self):
        """Whether the text is unreadable, e.g. when entering passwords"""
        return getattr(self, '_obscured', False)

    @obscured.setter
    def obscured(self, obscured):
        self._obscured = bool(obscured)
        self.signal.emit('dialog_updated', self)

    @property
    def read_only(self):
        """Whether the user can change the text"""
        return getattr(self, '_read_only', False)

    @read_only.setter
    def read_only(self, read_only):
        self._read_only = bool(read_only)
        self.signal.emit('dialog_updated', self)

    def initialize(self, *, name, label, text='', validator=None, obscured=False, read_only=False):
        """
        Set internal state

        :param name: Name for internal use
        :param label: Name for user-facing use
        :param text: Initial text
        :param validator: Callable that gets text before job is finished. If
            `ValueError` is raised, it is displayed as a warning instead of
            finishing the job.
        :param validator: callable or None
        """
        self._name = str(name)
        self._label = str(label)
        self._validator = validator or (lambda _: None)
        self.signal.add('dialog_updated')
        self.signal.add('accepted')
        self.text = text
        self.obscured = obscured
        self.read_only = read_only

    def finish(self):
        """
        :meth:`send` current :attr:`text` and :meth:`finish`

        If `validator` raises :class:`ValueError`, pass it to :meth:`warn` and
        do not finish.
        """
        try:
            self._validator(self.text)
        except ValueError as e:
            self.warn(e)
        else:
            self.send(self.text)
            super().finish()
