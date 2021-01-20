"""
Get information from the user
"""

from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ChoiceJob(JobBase):
    """Prompt the user to choose from a set of values"""

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

    @property
    def focused(self):
        """Initially focused choice"""
        return self._focused

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
        self._choices = tuple(str(c) for c in choices)
        if len(self._choices) < 2:
            raise ValueError(f'choices must contain at least 2 items: {self._choices}')
        if focused is not None:
            if str(focused) not in self._choices:
                raise ValueError(f'Invalid choice: {focused}')
            else:
                self._focused = str(focused)
        else:
            self._focused = self._choices[0]

    def choice_selected(self, choice):
        """
        Must be called by the UI when the user makes a choice

        :param choice: Chosen value or index in :attr:`choices`

        :raise ValueError: if `choice` is not valid
        """
        if str(choice) in self._choices:
            self.send(str(choice))
        elif isinstance(choice, int):
            if 0 <= choice < len(self._choices):
                self.send(self._choices[choice])
            else:
                self.exception(ValueError(f'Invalid index: {choice}'))
        else:
            self.exception(ValueError(f'Invalid value: {choice}'))
        self.finish()
