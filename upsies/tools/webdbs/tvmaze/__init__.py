label = 'TVmaze'
_url_base = 'http://api.tvmaze.com'

from ..common import gather
from ._info import summary, title_english, title_original, type, year
from ._search import search
