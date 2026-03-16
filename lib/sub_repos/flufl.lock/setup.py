"""NFS-safe file locking with timeouts for POSIX and Windows."""

from setup_helpers import get_version, require_python
from setuptools import setup, find_namespace_packages


require_python(0x30600f0)
__version__ = get_version('flufl/lock/__init__.py')


with open('README.rst') as fp:
    readme = fp.read()


setup(
    name='flufl.lock',
    version=__version__,
    author='Barry Warsaw',
    author_email='barry@python.org',
    description=__doc__,
    long_description=readme,
    long_description_content_type='text/x-rst',
    license='Apache 2.0',
    keywords='locking locks lock',
    url='https://flufllock.readthedocs.io',
    download_url='https://pypi.python.org/pypi/flufl.lock',
    packages=find_namespace_packages(where='.', exclude=['test*', 'docs']),
    namespace_packages=['flufl'],
    include_package_data=True,
    package_data={
        'flufl.lock': ['flufl/lock/py.typed'],
        },
    # readthedocs builds fail unless zip_safe is False.
    zip_safe=False,
    python_requires='>=3.6',
    install_requires=[
        'atpublic',
        'psutil',
        'typing_extensions;python_version<"3.8"',
        ],
    project_urls={
        'Documentation': 'https://flufllock.readthedocs.io',
        'Source': 'https://gitlab.com/warsaw/flufl.lock.git',
        'Tracker': 'https://gitlab.com/warsaw/flufl.lock/issues',
        },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Development Status :: 6 - Mature',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        ],
    )
