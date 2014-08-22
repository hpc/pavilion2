try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Cluster Test Harness',
    'author': 'LANL',
    'url': 'git.lanl.gov/cwi/pavilion',
    'download_url': 'git@git.lanl.gov/cwi/pavilion',
    'author_email': 'cwi@lanl.gov.',
    'version': '0.9',
    'packages': ['PAV'],
    'packages': ['modules'],
    'packages': ['plugins'],
    'packages': ['special-pkgs/yapsy'],
    'scripts': [],
    'name': 'pavilion'
}

setup(**config)
