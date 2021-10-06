extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx_autorun',
]

autosummary_generate = True
html_show_sourcelink = False  # Don't show links to rST code

templates_path = ['_templates']

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}
