"""
Get information from the user
"""

import collections

from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ChoiceJob(JobBase):
    """
    Prompt the user to choose from a set of values

    This job adds the following signals to the :attr:`~.JobBase.signal`
    attribute:

        ``prompt_updated``
            Emitted when :attr:`choices` or :attr:`focused` is set. Registered
            callbacks get the sequence of choices and the index of the focused
            choice as positional arguments.

        ``chosen``
            Emitted when the user made a choice. Registered callbacks get the
            chosen item from :attr:`choices` as a positional argument.
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

        A choice is a :class:`tuple` with 2 or more items. The first item is a
        human-readable :class:`str` and the second item is any object. Any
        further items are preserved.
        """
        return getattr(self, '_choices', ())

    @choices.setter
    def choices(self, choices):
        valid_choices = []
        for choice in choices:
            if isinstance(choice, str):
                valid_choices.append((choice, choice))
            elif isinstance(choice, collections.abc.Sequence):
                if len(choice) < 2:
                    raise ValueError(f'Choice must be a 2-tuple, not {choice!r}')
                else:
                    valid_choices.append((str(choice[0]),) + tuple(choice[1:]))
            else:
                raise ValueError(f'Choice must be a 2-tuple, not {choice!r}')

        if len(valid_choices) < 2:
            raise ValueError(f'Choices must have at least 2 items: {choices!r}')

        prev_focused = self.focused
        self._choices = tuple(valid_choices)
        if prev_focused in valid_choices:
            self._focused_index = valid_choices.index(prev_focused)
        else:
            self._focused_index = 0

        self.signal.emit('prompt_updated', self._choices, self._focused_index)

    @property
    def focused(self):
        """
        Currently focused choice

        Setting this property to `None` focuses the first choice in
        :attr:`choices`.

        Setting this property to an :class:`in` focuses the choice at that index
        in :attr:`choices`.

        Setting this property to a :class:`str` focuses the first choice in
        :attr:`choices` for which its first item is equal to it. If no such
        choice exists, :class:`ValueError` is raised.

        Setting this property to any other value assumes that value is a choice
        in :attr:`choices` and it is focused. If that value does not exist,
        :class:`ValueError` is raised.
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
        elif isinstance(focused, str):
            for i, choice in enumerate(self.choices):
                if focused == choice[0] or focused == choice[1]:
                    self._focused_index = i
                    break
            else:
                raise ValueError(f'Invalid choice: {focused!r}')
        else:
            if focused in self.choices:
                self._focused_index = self.choices.index(focused)
            else:
                raise ValueError(f'Invalid choice: {focused!r}')

        self.signal.emit('prompt_updated', self.choices, self._focused_index)

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
        self.signal.add('prompt_updated')
        self.signal.add('chosen')
        self.choices = choices
        self.focused = focused

    def choice_selected(self, choice):
        """
        Must be called by the UI when the user makes a choice

        :param choice: Index in :attr:`choices`, item in :attr:`choices`, first
            or second item of a sequence in :attr:`choices` or `None` (user
            refused to choose)
        """
        def choose(choice):
            # Machine-readable choice
            self.signal.emit('chosen', choice)
            # User-readable string
            self.send(choice[0])

        if choice in self.choices:
            choose(choice)
        elif isinstance(choice, int):
            try:
                choose(self.choices[choice])
            except IndexError:
                self.exception(ValueError(f'Invalid choice: {choice!r}'))
        elif isinstance(choice, str):
            for c in self.choices:
                if choice == c[0] or choice == c[1]:
                    choose(c)
                    break
            else:
                self.exception(ValueError(f'Invalid choice: {choice!r}'))
        elif choice is not None:
            self.exception(ValueError(f'Invalid choice: {choice!r}'))
        self.finish()
