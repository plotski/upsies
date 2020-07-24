from prompt_toolkit import styles

# Remove defaults
styles.defaults.PROMPT_TOOLKIT_STYLE.clear()
styles.defaults.WIDGETS_STYLE.clear()

style = styles.Style([
    ('output', ''),
    ('result', 'bg:#333 fg:#eee'),
    ('info', 'fg:#bb9'),
    ('error', 'bg:#333 fg:#ff4f00 bold'),
    ('input-field', 'bg:#aaa fg:#000'),
    ('text-field', 'bg:#333 fg:#ddd'),
    ('field-label', 'bold'),
    ('search-result', 'bg:#333 fg:#ccc'),
    ('search-result focused', 'bg:#aaa fg:#000'),
    ('progress-bar', 'bg:#333 fg:#ccc'),
    ('progress-bar.progress', 'reverse'),
])
