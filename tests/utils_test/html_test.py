import pytest

from upsies import errors
from upsies.utils import html


def test_html_returns_BeautifulSoup_instance(mocker):
    mocker.patch('bs4.BeautifulSoup', return_value='mock html')
    assert html.parse('<html>foo</html>') == 'mock html'

def test_html_raises_ContentError(mocker):
    mocker.patch('bs4.BeautifulSoup', side_effect=ValueError('Too many tags!'))
    with pytest.raises(errors.ContentError, match=r'^Invalid HTML: Too many tags!$'):
        html.parse('<html>foo</html>')


def test_dump_writes_string(tmp_path):
    html.dump('<html>foo</html>', tmp_path / 'foo.html')
    assert (tmp_path / 'foo.html').read_text() == '<html>\n foo\n</html>'

def test_dump_writes_BeautifulSoup_instance(tmp_path):
    from bs4 import BeautifulSoup
    doc = BeautifulSoup('<html>foo</html>', features='html.parser')
    html.dump(doc, tmp_path / 'foo.html')
    assert (tmp_path / 'foo.html').read_text() == '<html>\n foo\n</html>'


def test_as_text_removes_html_tags():
    assert html.as_text('<html>foo</html>') == 'foo'

def test_as_text_deduplicates_whitespace():
    assert html.as_text('<html>foo</html>') == 'foo'
    assert html.as_text('\n<html>  f o   o\n\n bar</html>\n\n') == 'f o o\nbar'


def test_purge_javascript():
    string = (
        '<html>\n'
        'a\n'
        '<script>foo</script>\n'
        'b<script with="attribute">bar</script>\n'
        'c\n'
        '<script>\n'
        '    baz\n'
        '</script>\n'
        '</html>\n'
    )
    assert html.purge_javascript(string) == (
        '<html>\n'
        'a\n'
        '\n'
        'b\n'
        'c\n'
        '\n'
        '</html>\n'
    )
