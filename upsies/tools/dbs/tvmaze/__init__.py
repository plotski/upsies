label = 'TVmaze'
_url_base = 'https://api.tvmaze.com'

from .._common import info
from ._info import summary, title_english, title_original, year
from ._search import search
