from unittest.mock import Mock, call

import pytest

from upsies.utils import update


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


@pytest.mark.parametrize(
    argnames='current, release, prerelease, exp_newer_version',
    argvalues=(
        # Running stable
        ('2021.06.20', '2021.06.20', '2021.06.20', None),
        ('2021.06.20', '2021.06.20', '2021.06.21alpha', None),
        ('2021.06.20', '2021.06.20', '2021.06.21', None),
        ('2021.06.20', '2021.06.21', '2021.06.21', '2021.06.21'),
        ('2021.06.20', '2021.06.21', '2021.06.21alpha', '2021.06.21'),
        ('2021.06.20', '2021.06.21', '2021.06.22alpha', '2021.06.21'),
        ('2021.06.20', '2021.06.20', None, None),
        ('2021.06.20', '2021.06.22', None, '2021.06.22'),

        # Running prerelease
        ('2021.06.25alpha', '2021.06.20', '2021.06.20alpha', None),
        ('2021.06.25alpha', '2021.06.20', '2021.06.25alpha', None),
        ('2021.06.25alpha', '2021.06.20', '2021.06.26alpha', '2021.06.26alpha'),
        ('2021.06.25alpha', '2021.06.26', '2021.06.26alpha', '2021.06.26'),
        ('2021.06.25alpha', '2021.06.26', '2021.06.27alpha', '2021.06.27alpha'),
    ),
)
@pytest.mark.asyncio
async def test_get_newer_version(current, release, prerelease, exp_newer_version, mocker):
    mocker.patch('upsies.utils.update._get_versions', AsyncMock(return_value=(current, release, prerelease)))
    newer_version = await update.get_newer_version()
    assert newer_version == exp_newer_version


@pytest.mark.parametrize(
    argnames='current, release, prerelease, exp_versions',
    argvalues=(
        ('2021.06.20', '2021.06.21', '2021.06.25alpha', ('2021.06.20', '2021.06.21', None)),
        ('2021.06.20alpha', '2021.06.21', '2021.06.25alpha', ('2021.06.20alpha', '2021.06.21', '2021.06.25alpha')),
    ),
)
@pytest.mark.asyncio
async def test_get_versions(current, release, prerelease, exp_versions, mocker):
    mocker.patch('upsies.utils.update.__version__', current)
    mocker.patch('upsies.utils.update._get_latest_release', AsyncMock(return_value=release))
    mocker.patch('upsies.utils.update._get_latest_prerelease', AsyncMock(return_value=prerelease))
    versions = await update._get_versions()
    assert versions == exp_versions


@pytest.mark.parametrize(
    argnames='versions, exp_latest_version',
    argvalues=(
        (['2021.6.20', '2021.8.10', '2023.4.7'], '2023.4.7'),
        ([], None),
    ),
)
@pytest.mark.asyncio
async def test_get_latest_release(versions, exp_latest_version, mocker):
    response_mock = Mock(
        json=Mock(return_value={
            'releases': {v: f'info about {v!r}' for v in versions},
        }),
    )
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=response_mock))
    latest_version = await update._get_latest_release()
    if exp_latest_version:
        assert latest_version == update._fix_version(exp_latest_version)
    else:
        assert latest_version is None
    assert get_mock.call_args_list == [
        call(
            url=update._PYPI_URL,
            timeout=update._REQUEST_TIMEOUT,
            cache=True,
            max_cache_age=update._MAX_CACHE_AGE,
        ),
    ]


@pytest.mark.parametrize(
    argnames='init_file_string, exp_latest_version',
    argvalues=(
        ("foo\n__version__='2021.06.20'\nbar\n", '2021.06.20'),
        ('foo\n__version__="2021.06.20"\nbar\n', '2021.06.20'),
        ("foo\n__version__ = '2021.06.20'\nbar\n", '2021.06.20'),
        ('foo\n__version__ = "2021.06.20"\nbar\n', '2021.06.20'),
        ("foo\n__venison__='2021.06.20'\nbar\n", None),
    ),
)
@pytest.mark.asyncio
async def test_get_latest_prerelease(init_file_string, exp_latest_version, mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=init_file_string))
    latest_version = await update._get_latest_prerelease()
    if exp_latest_version:
        assert latest_version == exp_latest_version
    else:
        assert latest_version is None
    assert get_mock.call_args_list == [
        call(
            url=update._REPO_URL,
            timeout=update._REQUEST_TIMEOUT,
            cache=True,
            max_cache_age=update._MAX_CACHE_AGE,
        ),
    ]


@pytest.mark.parametrize(
    argnames='version, exp_version',
    argvalues=(
        ('0.0.1', '0.0.1'),
        ('2021.6.20', '2021.06.20'),
        ('2021.6.20.1', '2021.06.20.1'),
        ('2021.10.20', '2021.10.20'),
    ),
)
def test_fix_version(version, exp_version):
    assert update._fix_version(version) == exp_version
