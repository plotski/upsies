import functools

from ... import jobs as _jobs
from ...utils import cache, fs

import logging  # isort:skip
_log = logging.getLogger(__name__)


class SubcommandBase:
    def __init__(self, args, config):
        self._args = args
        self._config = config

    @property
    def args(self):
        return self._args

    @property
    def config(self):
        return self._config


class torrent(SubcommandBase):
    @cache.property
    def jobs(self):
        return (
            _jobs.torrent.Torrent(
                homedir=fs.projectdir(self.args.path, self.args.tracker),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.path,
                announce_url=self.config.get(self.args.tracker, 'announce'),
                trackername=self.args.tracker,
                source=self.args.source or self.config.get(self.args.tracker, 'source'),
                exclude_regexs=self.config.get(self.args.tracker, 'exclude'),
            ),
        )


class screenshots(SubcommandBase):
    @cache.property
    def jobs(self):
        return (
            _jobs.screenshots.Screenshots(
                homedir=fs.projectdir(self.args.path, self.args.tracker),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.path,
                timestamps=self.args.timestamps,
                number=self.args.number,
                upload_to=self.args.upload,
            ),
        )


@functools.lru_cache(maxsize=None)
def make_search_command(db_name):
    @cache.property
    def jobs(self):
        return (
            _jobs.search.Search(
                homedir=fs.projectdir(self.args.path, self.args.tracker),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.path,
                db=db_name,
            ),
        )

    clsname = f'{db_name.capitalize()}Search'
    bases = (SubcommandBase,)
    attrs = {'jobs': jobs}
    return type(clsname, bases, attrs)


class release_name(SubcommandBase):
    @cache.property
    def jobs(self):
        # Include the original and English title in the release name.
        # IMDb seems to be best.
        ImdbSearch = make_search_command('imdb')
        imdb_job = ImdbSearch(args=self.args, config=self.config).jobs[0]
        rn_job = _jobs.release_name.ReleaseName(
            homedir=fs.projectdir(self.args.path, self.args.tracker),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.path,
        )
        imdb_job.on_id_selected(rn_job.fetch_info)
        return (imdb_job, rn_job)


class submit(SubcommandBase):
    @cache.property
    def jobs(self):
        try:
            tracker = getattr(_jobs.submit, self.args.tracker)
        except AttributeError:
            raise ValueError(f'Unknown tracker: {self.args.tracker}')

        _log.debug('Tracker: %r', tracker)
        _log.debug('Submission class: %r', tracker.Submission)
        sub = tracker.Submission(
            homedir=fs.projectdir(self.args.path, self.args.tracker),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.path,
            announce_url=self.config.get('nbl', 'announce')
        )
        _log.debug('Tracker jobs: %r', sub.jobs)
        return sub.jobs
