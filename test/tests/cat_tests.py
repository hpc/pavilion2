import io

from pavilion import arguments
from pavilion import commands
from pavilion.unittest import PavTestCase


class StatusTests(PavTestCase):

    def test_cat(self):
        """Checking cat command functionality"""
        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['echo "hello world"'] * 10
        test = self._quick_test(test_cfg)

        cat_cmd = commands.get_command('cat')
        cat_cmd.outfile = cat_cmd.errfile = io.StringIO()

        arg_parser = arguments.get_parser()
        arg_sets = (['cat', test.full_id, 'run.tmpl'],)
        for arg_set in arg_sets:
            args = arg_parser.parse_args(arg_set)
            cat_cmd.run(self.pav_cfg, args)

            with open(str(test.path/arg_set[-1]), 'r') as out_file:
                true_out = out_file.read() + '\n'
                cat_out = cat_cmd.outfile.getvalue()
                self.assertEqual(cat_out, true_out)
