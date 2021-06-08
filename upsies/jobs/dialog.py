"""
Get information from the user
"""

import collections

from .. import errors, utils
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
            set or when :attr:`choices` is modified. Registered callbacks get
            the job instance as a positional argument.

        ``chosen``
            Emitted when the :attr:`choice` property is set or when the job's
            cache is read. Registered callbacks get :attr:`choice` as a
            positional argument.
    """

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

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

        When setting this property, focus is preserved if the value of the
        focused choice exists in the new choices. Otherwise, the first choice is
        focused.
        """
        return getattr(self, '_choices', ())

    @choices.setter
    def choices(self, choices):
        # Build new list of choices
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

        # Remember current focus
        prev_focused = self.focused

        # Set new choices
        self._choices = utils.MonitoredList(
            valid_choices,
            callback=lambda _: self.signal.emit('dialog_updated', self),
        )

        # Try to restore focus
        self._focused_index = 0
        if prev_focused:
            prev_label, prev_value = prev_focused
            for index, (label, value) in enumerate(valid_choices):
                if value == prev_value:
                    self._focused_index = index
                    break

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

        While :attr:`~.base.JobBase.output` contains the user-readable string
        (first item of the chosen item in :attr:`choices`), this is the object
        attached to it (second item).

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
            self.signal.emit('chosen', choice[1])
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

    def set_label(self, identifier, new_label):
        """
        Assign new label to choice

        :param identifier: Choice (2-tuple of (<current label>, <value>) or the
            current label or value of a choice
        :param new_label: New label for the choice defined by `identifier`

        Do nothing if `identifier` doesn't match any choice.
        """
        new_choices = []
        for label, value in tuple(self.choices):
            if identifier == label or identifier == value or identifier == (label, value):
                new_choices.append((str(new_label), value))
            else:
                new_choices.append((label, value))
        if self.choices != new_choices:
            self.choices = new_choices

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
        self.signal.record('chosen')
        self.signal.register('chosen', lambda choice: setattr(self, '_choice', choice))
        self.choices = choices
        self.focused = focused


class TextFieldJob(JobBase):
    """
    Ask the user for text input

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``dialog_updating``
            Emitted when :meth:`fetch_text`` is called to indicate activity.
            Registered callbacks get the job instance as a positional argument.

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
    def text(self):
        """Current text"""
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

    @property
    def exit_code(self):
        """
        Always exit with ``0``

        Instead of exiting with a non-zero exit code, the application should
        :meth:`warn` the user about invalid values. This is done by providing a
        `validator`.
        """
        if self.is_finished:
            return 0

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
        :param bool obscured: Whether :attr:`obscured` is set to `True`
            initially
        :param bool read_only: Whether :attr:`read_only` is set to `True`
            initially
        """
        self._name = str(name)
        self._label = str(label)
        self._validator = validator or (lambda _: None)
        self.signal.add('dialog_updating')
        self.signal.add('dialog_updated')
        self.signal.add('accepted')
        self.text = text
        self.obscured = obscured
        self.read_only = read_only

    def send(self, output):
        """
        Validate `output` before actually sending it

        Pass `output` to `validator`. If :class:`ValueError` is raised, pass it
        to :meth:`warn` and do not finish. Otherwise, pass `output` to
        :meth:`~.base.JobBase.send` and :meth:`~.base.JobBase.finish` this job.
        """
        try:
            self._validator(output)
        except ValueError as e:
            self.warn(e)
        else:
            super().send(output)
            super().finish()

    async def fetch_text(self, coro, default_text=None, finish_on_success=False, error_is_fatal=False):
        """
        Get :attr:`text` from coroutine

        :param coro: Coroutine that returns the new :attr:`text`
        :param default_text: String to use if `coro` raises
            :class:`~.errors.RequestError` or `None` to keep the original
            :attr:`text` in that case
        :param finish_on_success: Whether to call :meth:`finish` after setting
            :attr:`text` to `coro` return value
        :param error_is_fatal: Whether to call :meth:`error` and :meth:`finish`
            if `coro` raises :class:`~.errors.RequestError` instead of
            :meth:`warn`
        """
        self.read_only = True
        self.signal.emit('dialog_updating', self)
        try:
            # Try to set text field value, e.g. from IMDb
            text = await coro
        except errors.RequestError as e:
            # Inform user about failure and allow them to make manual
            # adjustments to default text
            if error_is_fatal:
                self.error(e)
            else:
                self.warn(e)
            if default_text is not None:
                self.text = default_text
        else:
            # send() also finishes. This is important for reading from cache.
            if finish_on_success:
                self.send(text)
            else:
                self.text = text
        finally:
            # Always re-enable text field after we're done messing with it
            self.read_only = False
