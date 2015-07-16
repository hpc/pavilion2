try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Pavilion - High Performance Cluster Testing Framework',
    'long_description': 'Software framework and tools for testing and analyzing HPC system health',
    'author': 'LANL',
    'url': 'git.lanl.gov/cwi/pavilion',
    'download_url': 'git@git.lanl.gov/cwi/pavilion',
    'author_email': 'cwi@lanl.gov',
    'version': '0.86',
    'packages': ['PAV'],
    'packages': ['test'],
    'name': 'pavilion'
}

setup(**config)
