try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Cluster Test Harness',
    'author': 'LANL',
    'url': 'URL to get it at.',
    'download_url': 'Where to download it.',
    'author_email': 'cwi@lanl.gov.',
    'version': '0.1',
    'install_requires': ['nose'],
    'packages': ['CLTH'],
    'scripts': [],
    'name': 'projectname'
}

setup(**config)
