try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Cluster Test Harness',
    'author': 'LANL',
    'url': 'git.lanl.gov/cwi/pavilion',
    'download_url': 'git@git.lanl.gov/cwi/pavilion',
    'author_email': 'cwi@lanl.gov',
    'version': '0.28',
    'packages': ['PAV'],
    'packages': ['test'],
    'name': 'pavilion'
}

setup(**config)
