import io

from unittest_ex import TestCaseEx
from . import test_appliance
from . import test_canonical, test_emitter, test_errors, test_input_output, \
    test_mark, test_reader, test_recursive, test_resolver, test_structure, test_tokens


class YamlTests(TestCaseEx):

    def test_yaml(self):

        test_collections = []
        for module in [
                test_canonical,
                test_emitter,
                test_errors,
                test_input_output,
                test_mark,
                test_reader,
                test_recursive,
                test_resolver,
                test_structure,
                test_tokens]:
            test_collections.append(module.__dict__)

        outfile = io.StringIO()
        result = test_appliance.run(test_collections, args={}, outfile=outfile)

        self.assertTrue(result, msg=outfile.getvalue())
