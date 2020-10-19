import setuptools
import re

def get_long_description():
    with open('README.md', 'r') as f:
        return f.read()

def get_var(name):
    with open('upsies/__init__.py') as f:
        content = f.read()
        match = re.search(rf'''^{name}\s*=\s*['"]([^'"]*)['"]''',
                          content, re.MULTILINE)
        if match:
            return match.group(1)
        else:
            raise RuntimeError(f'Unable to find {name}')

setuptools.setup(
    name=get_var('__project_name__'),
    version=get_var('__version__'),
    author=get_var('__author__'),
    author_email=get_var('__author_email__'),
    description=get_var('__description__'),
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    url=get_var('__homepage__'),
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    ],
    python_requires='>=3.6',
    install_requires=[
        # FIXME: imdbpie depends on attrs>=18.1.0,<19.0.0
        #        aiohttp depends on attrs>=17.3.0
        'attrs<19.*,>18.1.*',

        'aiohttp==3.6.*',
        # FIXME: We use yarl, but aiohttp has its own ideas about the best
        #        version of it. aiohttp 3.6.3 pinned yarl to 1.6.0 while yarl
        #        1.6.2 was the most recent release. If we just depend on "yarl"
        #        (no version), pip installs the most recent version even though
        #        aiohttp depends on 1.6.0.
        #
        #        This seems to be fixed by pip's new resolver which can be
        #        enabled with --use-feature=2020-resolver, but that's not very
        #        user-friendly.  'yarl',

        'imdbpie==5.6.*',
        'beautifulsoup4==4.*',
        'guessit==3.*',
        'natsort==7.*',
        'prompt_toolkit==3.*,>=3.0.6',
        'pyimgbox==0.3.*',
        'pyxdg',
        'torf==3.*',
    ],
    entry_points={'console_scripts': ['upsies = upsies.uis.tui:main']},
)
