try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Pavilion - High Performance Cluster Testing Framework',
    'long_description': 'Software framework and tools for testing and analyzing HPC system health',
    'author': 'DOE',
    'download_url': 'https://github.com/losalamos/Pavilion',
    'author_email': 'dejager@lanl.gov',
    'version': '1.1.11',
    'packages': ['PAV', 'test'],
    'name': 'pavilion'
}

setup(**config)
