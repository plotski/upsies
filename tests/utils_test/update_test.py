from unittest.mock import Mock, call

import packaging
import pytest

from upsies import __project_name__
from upsies.utils import update


class AsyncMock(Mock):
    def __call__(self, *args, **kwargs):
        async def coro(_sup=super()):
            return _sup.__call__(*args, **kwargs)
        return coro()

    def __await__(self):
        return self().__await__()


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


@pytest.mark.parametrize(
    argnames='current, release, prerelease, exp_latest_version',
    argvalues=(
        ('2021.06.10', '2021.06.10', '2021.06.10', '2021.06.10'),
        ('2021.06.10', '2021.06.15', '2021.06.20alpha', '2021.06.15'),

        ('2021.06.20alpha', '2021.06.15', '2021.06.20alpha', '2021.06.20alpha'),
        ('2021.06.20alpha', '2021.06.15', '2021.06.25alpha', '2021.06.25alpha'),

        ('2021.06.20alpha', '2021.06.15', '2021.06.20alpha1', '2021.06.20alpha1'),
        ('2021.06.20alpha2', '2021.06.15', '2021.06.25alpha3', '2021.06.25alpha3'),
    ),
)
@pytest.mark.asyncio
async def test_get_latest_version(current, release, prerelease, exp_latest_version, mocker):
    get_latest_release_mock = mocker.patch('upsies.utils.update._get_latest_release_version',
                                           AsyncMock(return_value=release))
    get_latest_prerelease_mock = mocker.patch('upsies.utils.update._get_latest_prerelease_version',
                                              AsyncMock(return_value=prerelease))
    mocker.patch('upsies.utils.update.__version__', current)
    latest_version = await update.get_latest_version()
    assert latest_version == exp_latest_version
    if packaging.version.parse(current).is_prerelease:
        assert get_latest_release_mock.call_args_list == []
        assert get_latest_prerelease_mock.call_args_list == [call()]
    else:
        assert get_latest_release_mock.call_args_list == [call()]
        assert get_latest_prerelease_mock.call_args_list == []


@pytest.mark.parametrize(
    argnames='versions, exp_latest_version',
    argvalues=(
        (['2021.6.20', '2021.8.10', '2023.4.7'], '2023.4.7'),
        ([], None),
    ),
)
@pytest.mark.asyncio
async def test_get_latest_release_version(versions, exp_latest_version, mocker):
    response_mock = Mock(
        json=Mock(return_value={
            'releases': {v: f'info about {v!r}' for v in versions},
        }),
    )
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=response_mock))
    latest_version = await update._get_latest_release_version()
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
async def test_get_latest_prerelease_version(init_file_string, exp_latest_version, mocker):
    get_mock = mocker.patch('upsies.utils.http.get', AsyncMock(return_value=init_file_string))
    latest_version = await update._get_latest_prerelease_version()
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
    argnames='current_version, latest_version, message_is_returned',
    argvalues=(
        ('2021.06.19', '2021.06.20', True),
        ('2021.06.20', '2021.06.20', False),
        ('2021.06.19', '2021.06.18', False),

        ('2021.06.20alpha', '2021.06.20', True),
        ('2021.06.20alpha', '2021.06.20alpha', False),
        ('2021.06.20', '2021.06.20alpha', False),

        ('2021.06.20', '2021.06.21alpha', False),
        ('2021.06.20alpha', '2021.06.21alpha', True),
        ('2021.06.20alpha', '2021.06.21', True),

        ('2021.06.21alpha0', '2021.06.21alpha1', True),
        ('2021.06.21alpha1', '2021.06.21alpha1', False),
        ('2021.06.21alpha1', '2021.06.21alpha0', False),
    ),
)
@pytest.mark.asyncio
async def test_get_update_message(current_version, latest_version, message_is_returned, mocker):
    get_latest_version_mock = mocker.patch('upsies.utils.update.get_latest_version',
                                           AsyncMock(return_value=latest_version))
    mocker.patch('upsies.utils.update.__version__', current_version)
    message = await update.get_update_message()
    if message_is_returned:
        exp_message = 'Latest {__project_name__} version: {latest_version}'.format(
            __project_name__=__project_name__,
            latest_version=latest_version,
        )
        assert message == exp_message
    else:
        assert message is None

    assert get_latest_version_mock.call_args_list == [call()]
