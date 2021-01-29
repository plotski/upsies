"""
TUI representation of :class:`jobs <upsies.jobs.base.JobBase>`
"""

from ....utils import subclasses, submodules
from .base import JobWidgetBase


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
    widget_clses = subclasses(JobWidgetBase, submodules(__package__))
    for widget_cls in widget_clses:
        if widget_cls.__name__ == widget_cls_name:
            return widget_cls(job)
    raise RuntimeError(f'No widget class found for job: {job!r}')
