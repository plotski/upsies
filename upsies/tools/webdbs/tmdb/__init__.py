label = 'TMDb'
_url_base = 'http://themoviedb.org'

from ..common import gather
from ._info import summary, title_english, title_original, type, year
from ._search import search
