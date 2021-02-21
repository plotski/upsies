"""
Highlighting for :class:`job widgets <upsies.uis.tui.widgets.JobWidget>`
"""

from prompt_toolkit import styles

# flake8: noqa: E241 multiple spaces after ','

# Remove defaults
styles.defaults.PROMPT_TOOLKIT_STYLE.clear()
styles.defaults.WIDGETS_STYLE.clear()

# https://python-prompt-toolkit.readthedocs.io/en/master/pages/advanced_topics/styling.html

style = styles.Style([
    ('default',                       ''),
    ('label',                         'bold'),

    ('output',                        ''),
    ('warning',                       'fg:#fe0 bold'),
    ('error',                         'fg:#f60 bold'),

    ('info',                          'bg:#222 fg:#dd5'),
    ('info.progressbar',              ''),
    ('info.progressbar.progress',     'reverse'),

    ('dialog',                        'bg:#222 fg:#5dd'),

    ('dialog.text',                   ''),

    ('dialog.choice',                 ''),
    ('dialog.choice.focused',         'reverse'),

    ('dialog.search',                 'bg:default'),
    ('dialog.search.label',           'bold underline'),
    ('dialog.search.query',           'bg:#222'),
    ('dialog.search.info',            'bg:#222'),
    ('dialog.search.results',         'bg:#222'),
    ('dialog.search.results.focused', 'reverse'),
])
