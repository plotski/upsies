import functools

from ... import errors
from ... import jobs as _jobs
from ...tools import client, dbs
from ...utils import cache, fs

import logging  # isort:skip
_log = logging.getLogger(__name__)


def _get_client(config, clientname):
    if clientname:
        try:
            client_module = getattr(client, clientname)
        except AttributeError:
            raise errors.ConfigError(f'No such client: {clientname}')
        else:
            client_config = config['clients'][clientname]
            _log.debug('Client config: %r', client_config)
            return client_module.ClientApi(**client_config)


def _get_tracker_section(config, trackername):
    try:
        return config['trackers'][trackername]
    except KeyError:
        raise errors.ConfigError(f'Unknown tracker: {trackername!r}')


def _get_tracker_option(config, trackername, option):
    if trackername is None:
        raise errors.ConfigError('Missing argument: --tracker, -t')
    try:
        tracker = config['trackers'][trackername]
    except KeyError:
        raise errors.ConfigError(f'Unknown tracker: {trackername!r}')
    else:
        return tracker[option]


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
        tracker = _get_tracker_section(self.config, self.args.tracker)
        return (
            _jobs.torrent.CreateTorrentJob(
                homedir=fs.projectdir(self.args.path),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.path,
                announce_url=tracker['announce'],
                trackername=self.args.tracker,
                source=tracker['source'],
                exclude_regexs=tracker['exclude'],
                add_to=_get_client(self.config, self.args.add_to),
                copy_to=self.args.copy_to,
            ),
        )


class screenshots(SubcommandBase):
    @cache.property
    def jobs(self):
        return (
            _jobs.screenshots.ScreenshotsJob(
                homedir=fs.projectdir(self.args.path),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.path,
                timestamps=self.args.timestamps,
                number=self.args.number,
                upload_to=self.args.upload_to,
            ),
        )


class mediainfo(SubcommandBase):
    @cache.property
    def jobs(self):
        return (
            _jobs.mediainfo.MediainfoJob(
                homedir=fs.projectdir(self.args.path),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.path,
            ),
        )


@functools.lru_cache(maxsize=None)
def make_search_command(db_name):
    @cache.property
    def jobs(self):
        return (
            _jobs.search.SearchDbJob(
                homedir=fs.projectdir(self.args.path),
                ignore_cache=self.args.ignore_cache,
                content_path=self.args.path,
                db=db_name,
            ),
        )

    clsname = f'search_{db_name}'
    bases = (SubcommandBase,)
    attrs = {'jobs': jobs}
    return type(clsname, bases, attrs)


class release_name(SubcommandBase):
    @cache.property
    def jobs(self):
        # To be able to fetch the correct title, original title, year, etc, we
        # need to prompt for an ID first. IMDb seems to be best.
        search_imdb = make_search_command('imdb')
        imdb_job = search_imdb(args=self.args, config=self.config).jobs[0]
        rn_job = _jobs.release_name.ReleaseNameJob(
            homedir=fs.projectdir(self.args.path),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.path,
        )
        db = getattr(dbs, 'imdb')
        imdb_job.on_output(functools.partial(rn_job.fetch_info, db=db))
        return (imdb_job, rn_job)


class submit(SubcommandBase):
    @cache.property
    def jobs(self):
        try:
            tracker = getattr(_jobs.submit, self.args.tracker)
        except AttributeError:
            raise ValueError(f'Unknown tracker: {self.args.tracker}')

        _log.debug('Tracker: %r', self.args.tracker)
        _log.debug('Submission class: %r', tracker.SubmissionJob)
        sub = tracker.SubmissionJob(
            homedir=fs.projectdir(self.args.path),
            ignore_cache=self.args.ignore_cache,
            content_path=self.args.path,
            args=self.args,
            config=_get_tracker_section(self.config, self.args.tracker),
        )
        _log.debug('Tracker jobs: %r', sub.jobs)
        return sub.jobs
