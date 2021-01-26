"""
Get information from the user
"""

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
            callbacks get no arguments.
    """

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

    @property
    def choices(self):
        """Sequence of strings the user can choose from"""
        return self._choices

    @choices.setter
    def choices(self, choices):
        choices = tuple(str(c) for c in choices)
        if len(choices) < 2:
            raise ValueError(f'Choices must have at least 2 items: {choices}')
        else:
            self._choices = choices
        if getattr(self, '_focused', None) not in choices:
            self._focused = self._choices[0]
        self.signal.emit('prompt_updated')

    @property
    def focused(self):
        """
        Currently focused choice

        Setting this property to `None` focuses the first item in
        :attr:`choices`.
        """
        return self._focused

    @focused.setter
    def focused(self, focused):
        if focused is None:
            self._focused = self.choices[0]
        else:
            focused = str(focused)
            if focused not in self.choices:
                raise ValueError(f'Invalid choice: {focused}')
            else:
                self._focused = focused
        self.signal.emit('prompt_updated')

    def initialize(self, *, name, label, choices, focused=None):
        """
        Set internal state

        :param name: Name for internal use
        :param label: Name for user-facing use
        :param choices: Iterable of choices the user can make
        :param focused: One of the items in `choices` or `None` to pick the
            first one

        :raise ValueError: if `choices` is shorter than 2 or `focused` is not in
            `choices`
        """
        self._name = str(name)
        self._label = str(label)
        self._choices = self._focused = None
        self.signal.add('prompt_updated')
        self.choices = choices
        self.focused = focused

    def choice_selected(self, choice):
        """
        Must be called by the UI when the user makes a choice

        :param choice: Chosen value or index in :attr:`choices`

        :raise ValueError: if `choice` is not valid
        """
        if str(choice) in self.choices:
            self.send(str(choice))
        elif isinstance(choice, int):
            if 0 <= choice < len(self.choices):
                self.send(self.choices[choice])
            else:
                self.exception(ValueError(f'Invalid index: {choice}'))
        else:
            self.exception(ValueError(f'Invalid value: {choice}'))
        self.finish()
