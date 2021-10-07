import os
import sys

sys.path.append(os.path.abspath("./_ext"))

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'commands_reference',
]

autosummary_generate = True
html_show_sourcelink = False  # Don't show links to rST code

templates_path = ['_templates']

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}
