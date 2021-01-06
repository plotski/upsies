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
    ('error',                         'fg:#f60'),

    ('info',                          'bg:#222 fg:#dd5'),
    ('info.progressbar',              ''),
    ('info.progressbar.progress',     'reverse'),

    ('prompt',                        'bg:#222 fg:#5dd'),

    ('prompt.text',                   ''),

    ('prompt.choice',                 ''),
    ('prompt.choice.focused',         'reverse'),

    ('prompt.search',                 'bg:default'),
    ('prompt.search.label',           'bold underline'),
    ('prompt.search.query',           'bg:#222'),
    ('prompt.search.info',            'bg:#222'),
    ('prompt.search.results',         'bg:#222'),
    ('prompt.search.results.focused', 'reverse'),
])
