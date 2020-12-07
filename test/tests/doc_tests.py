import distutils.spawn
import pathlib
import subprocess
import unittest
from collections import defaultdict
from html.parser import HTMLParser
import shutil

from pavilion import wget
from pavilion.unittest import PavTestCase
from pavilion.utils import flat_walk

_SPHINX_PATH = shutil.which('sphinx-build')
_MIN_SPHINX_VERSION = (3, 0, 0)
_HAS_SPHINX = None


def has_sphinx():
    """Make sure we have a reasonably recent version of sphinx."""

    global _HAS_SPHINX

    if _HAS_SPHINX is not None:
        return _HAS_SPHINX

    if _SPHINX_PATH is None:
        _HAS_SPHINX = False
        return False

    proc = subprocess.run([_SPHINX_PATH, '--version'],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if proc.returncode != 0:
        # --version only exists for fairly recent versions
        # of sphinx build
        _HAS_SPHINX = False
        return False

    vers = proc.stdout.decode()
    vers = tuple(int(vpart) for vpart in vers.split()[-1].split('.'))
    if vers >= _MIN_SPHINX_VERSION:
        _HAS_SPHINX = True
        return True

    _HAS_SPHINX = False
    return False


class DocTests(PavTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.docs_built = False
        self.docs_build_out = None
        self.docs_build_ret = None

        self.bad_links = None
        self.external_links = None

    def setUp(self):
        """Build the docs only once."""

        if not self.docs_built:
            out, ret = self.build_docs()
            self.docs_built = True
            self.docs_build_out = out
            self.docs_build_ret = ret

    def build_docs(self):
        """Perform a clean build of the test documentation."""

        subprocess.call(['make', 'clean'],
                        cwd=(self.PAV_ROOT_DIR/'docs').as_posix(),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)

        cmd = ['make', 'html']

        proc = subprocess.Popen(
            cmd,
            cwd=(self.PAV_ROOT_DIR/'docs').as_posix(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        out, _ = proc.communicate(timeout=20)
        out = out.decode('utf8')
        result = proc.poll()

        return out, result

    def check_links(self):
        """Get the list of bad links, and the list of external links.
        Each is returned as a list of tuples of (origin_file, link). This
        assumes the docs have been built.

        returns: bad_links, external_links
        """

        if self.bad_links is not None:
            return self.bad_links, self.external_links

        web_root = self.PAV_ROOT_DIR/'docs'/'_build'

        # These will be non-locals in the scope of the html parser.
        seen_hrefs = set()
        seen_targets = set()
        external_links = set()

        class HREFParser(HTMLParser):
            """Parse the hrefs and anchor targets from a given html file."""

            def __init__(self, root, file_path):
                self.root = root
                self.path = file_path.relative_to(root)
                self.dir = file_path.parent

                seen_targets.add((self.path, ''))

                super().__init__()

            def handle_starttag(self, tag, attrs):
                """We want to record all the hrefs in the document. We also
                record every potential internal target."""

                nonlocal seen_hrefs
                nonlocal seen_targets
                nonlocal external_links

                if tag == 'a':
                    hrefs = [value for key, value in attrs if key == 'href']
                    if len(hrefs) > 1:
                        raise ValueError(
                            "'A' tag with more than one href: {}"
                            .format(attrs))

                    href_f = hrefs[0]

                    if href_f.startswith('#'):
                        anchor_f = href_f[1:]
                        seen_hrefs.add((self.path, (self.path, anchor_f)))
                    elif '://' in href_f:
                        external_links.add((self.path, href_f))
                    else:
                        if '#' in href_f:
                            file_loc, anchor_f = href_f.split('#', 2)
                        else:
                            file_loc, anchor_f = href_f, ''

                        file_loc = pathlib.Path(file_loc)

                        try:
                            file_loc = (self.dir/file_loc).resolve()
                            file_loc = file_loc.relative_to(self.root)
                        except FileNotFoundError:
                            pass

                        seen_hrefs.add((self.path, (file_loc, anchor_f)))

                id_ = [v for k, v in attrs if k == 'id']
                if id_:
                    seen_targets.add((self.path, id_[0]))

        for path in flat_walk(web_root):
            if path.is_dir():
                continue

            parser = HREFParser(web_root, path)

            if path.suffix == '.html':
                with path.open() as file:
                    parser.feed(file.read())

        bad_links = []
        for origin, ref in seen_hrefs:
            href, anchor = ref
            if ref not in seen_targets:
                if not (anchor or href.suffix == '.html' or
                        not (web_root / href).exists()):
                    # Skip links to non-html files that don't have an anchor
                    # and that exist.
                    continue

                if anchor:
                    href = '{}#{}'.format(href, anchor)

                bad_links.append((origin, href))

        # Save our results so we only have to do this once.
        self.bad_links = bad_links
        self.external_links = external_links

        return bad_links, external_links

    def test_doc_build(self):
        """Build the documentation and check for warnings/errors."""

        self.assertTrue(has_sphinx(),
                        msg="Sphinx missing. All other doc tests will skip.\n"
                            "See docs/README.md for instructions on setting "
                            "up Sphinx for testing.")

        self.assertEqual(self.docs_build_ret, 0,
                         msg="Error building docs:\n{}"
                             .format(self.docs_build_out))

        warnings = []
        for line in self.docs_build_out.split('\n'):
            if 'WARNING' in line:
                warnings.append(line)

        self.assertTrue(len(warnings) == 0,
                        msg='{} warnings in documentation build:\n{}\n\n{}'
                            .format(len(warnings), '\n'.join(warnings),
                                    self.docs_build_out))

    @unittest.skipIf(not has_sphinx(), "Could not find Sphinx.")
    def test_doc_links(self):
        """Verify the links in all the documentation. This shouldn't run as
        its own test, but as a subtest of our document making test so we
        don't have to make the docs twice."""

        bad_links, _ = self.check_links()

        link_desc = '\n'.join(['{} -> {}'.format(orig, href)
                               for orig, href in bad_links])

        self.assertTrue(bad_links == [],
                        msg="\nFound the following bad links:\n" + link_desc)

    @unittest.skipIf(not has_sphinx() or wget.missing_libs(),
                     "Could not find Sphinx (or maybe wget libs)")
    def test_doc_ext_links(self):
        """Check all the external doc links."""

        _, ext_links = self.check_links()

        origins_by_href = defaultdict(lambda: [])

        for origin, href in ext_links:
            origins_by_href[href].append(origin)

        # Check the external links too.
        for href in origins_by_href.keys():
            try:
                wget.head(self.pav_cfg, href)
            except wget.WGetError:
                self.fail("Could not fetch HEAD for doc external href '{}'"
                          .format(href))
