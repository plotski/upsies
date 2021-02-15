import pytest

from upsies import errors


def error_classes():
    clses = []
    for name in dir(errors):
        if not name.startswith('_'):
            cls = getattr(errors, name)
            if isinstance(cls, type) and issubclass(cls, Exception):
                clses.append(cls)
    return clses


@pytest.mark.parametrize(
    argnames='cls',
    argvalues=error_classes(),
)
def test_equality(cls):
    try:
        assert cls('foo') == cls('foo')
        assert cls('foo') != cls('bar')
        assert cls('foo') != ValueError('foo')
    # Some exceptions require more arguments
    except TypeError:
        pass
