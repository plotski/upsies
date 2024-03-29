import setuptools
import re

def get_long_description():
    with open('README.rst', 'r') as f:
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
    long_description_content_type='text/x-rst',
    url=get_var('__homepage__'),
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    ],
    python_requires='>=3.8',
    install_requires=[
        'beautifulsoup4==4.*',
        'chardet==5.*',
        'country-converter==0.7.*',
        'aiobtclientapi==1.*',
        'guessit==3.*,>=3.4.0',
        'httpx==0.*,>=0.20.0',
        'natsort==8.*',
        'packaging',
        'prompt_toolkit==3.*,>=3.0.6',
        'pyimgbox==1.*',
        'pyxdg',
        'torf==4.*',
        'Unidecode==1.3.*',
    ],
    entry_points={'console_scripts': ['upsies = upsies.uis.tui:main']},
)
