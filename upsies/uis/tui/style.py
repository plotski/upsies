from prompt_toolkit import styles

# Remove defaults
styles.defaults.PROMPT_TOOLKIT_STYLE.clear()
styles.defaults.WIDGETS_STYLE.clear()

style = styles.Style([
    ('job.output', ''),
    ('job.result', 'bg:#333 fg:#eee'),
    ('job.info', 'bg:#333 fg:#bb9'),
    ('job.error', 'bg:#333 fg:#ff4f00 bold'),
    ('textfield.input', 'bg:#999 fg:#000'),
    ('textfield.info', 'bg:#333 fg:#ddd'),
    ('textfield.label', 'bold'),
    ('search.result', 'bg:#333 fg:#ccc'),
    ('search.result focused', 'bg:#999 fg:#000'),
    ('progressbar', 'bg:#333 fg:#ccc'),
    ('progressbar.progress', 'reverse'),
])
