import json
import os
from pathlib import Path
from typing import Callable, Any

from pavilion import utils
from pavilion.exceptions import TestRunError


# pylint: disable=protected-access
def basic_attr(name, doc):
    """Create a basic attribute for the TestAttribute class. This
    will produce a property object with a getter and setter that
    simply retrieve or set the value in the self._attrs dictionary."""

    prop = property(
        fget=lambda self: self._attrs.get(name, None),
        fset=lambda self, val: self._attrs.__setitem__(name, val),
        doc=doc
    )

    return prop


class TestAttributes:
    """A object for accessing test attributes. TestRuns
    inherit from this, but it can be used by itself to access test
    information with less overhead.

    All attributes should be defined as getters and (optionally) setters.
    Getters should return None if no value is available.
    Getters should all have a docstring.

    **WARNING**

    This object is not thread or any sort of multi-processing safe. It relies
    on the expectation that the test lifecycle should generally mean there's
    only one instance of a test around that might change these values at any
    given time. The upside is that it's so unsafe, problems reveal themselves
    quickly in the unit tests.

    It's safe to set these values in the TestRun __init__, finalize,
    and gather_results.
    """

    serializers = {
        'suite_path': lambda p: p.as_posix(),
    }

    deserializers = {
        'created': utils.deserialize_datetime,
        'finished': utils.deserialize_datetime,
        'started': utils.deserialize_datetime,
        'suite_path': lambda p: Path(p) if p is not None else None,
    }

    COMPLETE_FN = 'RUN_COMPLETE'

    def __init__(self, path: Path, load=True):
        """Initialize attributes.
        :param path: Path to the test directory.
        :param load: Whether to autoload the attributes.
        """

        self.path = path

        self._attrs = {'warnings': []}

        self._complete = False

        # Set a logger more specific to this test.
        if load:
            self.load_attributes()

    ATTR_FILE_NAME = 'attributes'

    def save_attributes(self):
        """Save the attributes to file in the test directory."""

        attr_path = self.path/self.ATTR_FILE_NAME

        # Serialize all the values
        attrs = {}
        for key in self.list_attrs():
            val = getattr(self, key)
            if val is None:
                continue

            try:
                attrs[key] = self.serializers.get(key, lambda v: v)(val)
            except ValueError as err:
                self._add_warning(
                    "Error serializing attribute '{}' value '{}' for test run "
                    "'{}': {}".format(key, val, self.id, err.args[0])
                )

        tmp_path = attr_path.with_suffix('.tmp')
        with tmp_path.open('w') as attr_file:
            json.dump(attrs, attr_file)
        tmp_path.rename(attr_path)

    def load_attributes(self):
        """Load the attributes from file."""

        attr_path = self.path/self.ATTR_FILE_NAME

        attrs = {}
        if not attr_path.exists():
            self._attrs = self.load_legacy_attributes()
            return

        with attr_path.open() as attr_file:
            try:
                attrs = json.load(attr_file)
            except (json.JSONDecodeError, OSError, ValueError, KeyError) as err:
                raise TestRunError(
                    "Could not load attributes file: \n{}"
                    .format(err.args))

        for key, val in attrs.items():
            deserializer = self.deserializers.get(key)
            if deserializer is None:
                continue

            try:
                attrs[key] = deserializer(val)
            except ValueError:
                self._add_warning(
                    "Error deserializing attribute '{}' value '{}' for test "
                    "run '{}': {}".format(key, val, self.id, err.args[0]))

        self._attrs = attrs

    def load_legacy_attributes(self, initial_attrs=None):
        """Try to load attributes in older Pavilion formats, primarily before
        the attributes file existed."""

        initial_attrs = initial_attrs if initial_attrs else {}

        attrs = {
            'build_only': None,
            'build_name': None,
            'created':    self.path.stat().st_mtime,
            'finished':   self.path.stat().st_mtime,
            'id':         int(self.path.name),
            'rebuild':    False,
            'result':     None,
            'skipped':    None,
            'suite_path': None,
            'sys_name':   None,
            'user':       utils.owner(self.path),
            'uuid':       None,
            'warnings':   [],
        }

        build_origin_path = self.path / 'build_origin'
        if build_origin_path.exists():
            link_dest = os.readlink(build_origin_path.as_posix())
            attrs['build_name'] = link_dest.split('/')[-1]

        run_path = self.path / 'run.sh'
        if run_path.exists():
            attrs['started'] = run_path.stat().st_mtime

        res_path = self.path / 'results.json'
        if res_path.exists():
            attrs['finished'] = res_path.stat().st_mtime
            try:
                with res_path.open() as res_file:
                    results = json.load(res_file)
                attrs['result'] = results['result']
                attrs['sys_name'] = results['sys_name']
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        # Replace with items we got from the real attributes file
        attrs.update(initial_attrs)

        # These are so old always consider them complete
        self._complete = True

        return attrs

    LIST_ATTRS_EXCEPTIONS = ['complete']

    @classmethod
    def list_attrs(cls):
        """List the available attributes. This always operates on the
        base RunAttributes class, so it won't contain anything from child
        classes."""

        attrs = ['path']
        for key, val in TestAttributes.__dict__.items():
            if key in cls.LIST_ATTRS_EXCEPTIONS:
                continue
            if isinstance(val, property):
                attrs.append(key)
        attrs.sort()
        return attrs

    def attr_dict(self, include_empty=True, serialize=False):
        """Return the attributes as a dictionary."""

        attrs = {}
        for key in self.list_attrs():
            val = getattr(self, key)
            if serialize and key in self.serializers and val is not None:
                val = self.serializers[key](val)

            if val is not None or include_empty:
                attrs[key] = val

        attrs['complete'] = self.complete
        attrs['path'] = self.path.as_posix()

        return attrs

    @classmethod
    def attr_serializer(cls, attr) -> Callable[[Any], Any]:
        """Get the deserializer for this attribute, if any."""

        prop = cls.__dict__[attr]
        if hasattr(prop, 'serializer'):
            return prop.serializer
        else:
            return lambda d: d

    @classmethod
    def attr_deserializer(cls, attr) -> Callable[[Any], Any]:
        """Get the deserializer for this attribute, if any."""

        prop = cls.__dict__[attr]
        if hasattr(prop, 'deserializer'):
            return prop.deserializer
        else:
            return lambda d: d

    @classmethod
    def attr_doc(cls, attr):
        """Return the documentation string for the given attribute."""

        attr_prop = cls.__dict__.get(attr)

        if attr is None:
            return "Unknown attribute."

        return attr_prop.__doc__

    @property
    def complete(self) -> bool:
        """Returns whether the test is complete."""

        if not self._complete:
            run_complete_path = self.path / self.COMPLETE_FN
            # This will force a meta-data update on the directory.
            list(self.path.iterdir())

            if run_complete_path.exists():
                self._complete = True
                return True

        return self._complete

    build_only = basic_attr(
        name='build_only',
        doc="Only build this test, never run it.")
    build_name = basic_attr(
        name='build_name',
        doc="The name of the test run's build.")
    created = basic_attr(
        name='created',
        doc="When the test was created.")
    finished = basic_attr(
        name='finished',
        doc="The end time for this test run.")
    id = basic_attr(
        name='id',
        doc="The test run id (unique per working_dir at any given time).")
    name = basic_attr(
        name='name',
        doc="The full name of the test.")
    rebuild = basic_attr(
        name='rebuild',
        doc="Whether or not this test will rebuild it's build.")
    result = basic_attr(
        name='result',
        doc="The PASS/FAIL/ERROR result for this test. This is kept here for"
            "fast retrieval.")
    skipped = basic_attr(
        name='skipped',
        doc="Did this test's skip conditions evaluate as 'skipped'?")
    started = basic_attr(
        name='started',
        doc="The start time for this test run.")
    suite_path = basic_attr(
        name='suite_path',
        doc="Path to the suite_file that defined this test run."
    )
    sys_name = basic_attr(
        name='sys_name',
        doc="The system this test was started on.")
    user = basic_attr(
        name='user',
        doc="The user who created this test run.")
    uuid = basic_attr(
        name='uuid',
        doc="A completely unique id for this test run (test id's can rotate).")
    warnings = basic_attr(
        name='warnings',
        doc="Non-fatal internal errors in a TestRun."
    )

    def _add_warning(self, msg):
        """Add the given message to the warning attributes"""
        if msg not in self._attrs['warnings']:
            self._attrs['warnings'].append(msg)


def test_run_attr_transform(path):
    """A dir_db transformer to convert a test_run path into a dict of test
    attributes."""

    return TestAttributes(path).attr_dict(serialize=True)
