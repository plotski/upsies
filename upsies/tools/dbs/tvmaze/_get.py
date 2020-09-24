from ....utils import LazyModule

import logging  # isort:skip
_log = logging.getLogger(__name__)

bs4 = LazyModule(module='bs4', namespace=globals())


def summary(show):
    summary = show.get('summary', None)
    if summary:
        soup = bs4.BeautifulSoup(summary, 'html.parser')
        return '\n'.join(paragraph.text for paragraph in soup.find_all('p'))
    else:
        return ''


def year(show):
    premiered = show.get('premiered', None)
    if premiered:
        year = str(premiered).split('-')[0]
        if year.isdigit() and len(year) == 4:
            return year
    else:
        return ''


def genres(show):
    genres = show.get('genres', None)
    if genres:
        return tuple(str(g).lower() for g in genres)
    else:
        return ()


def country(show):
    network = show.get('network', None)
    if network:
        country = network.get('country', None)
        if country:
            name = country.get('name', None)
            if name:
                return name
    return ''
