from . import JobBase

import logging  # isort:skip
_log = logging.getLogger(__name__)


class ChoiceJob(JobBase):
    """
    Prompt the user to make a choice between a fixed set of values

    :param str name: Job's internal name
    :param str label: Job's displayed name
    :param choices: Iterable of choices
    :param focused: Initially focused choice

    :raise ValueError: if `choices` is shorter than 2 or `focused` is not in
        `choices`
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

    @property
    def focused(self):
        """Initially focused choice"""
        return self._focused

    def initialize(self, name, label, choices, focused=None):
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

    def execute(self):
        pass

    def choice_selected(self, choice):
        """
        Must be called by the UI when the user makes a choice

        :param choice: Chosen value or index in :attr:`choices`
        """
        choice_str = str(choice)
        assert choice_str in self._choices
        self.send(choice_str)
        self.finish()
