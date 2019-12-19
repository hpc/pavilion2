from pavilion import commands

class RunSeries(commands.Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='run_series',
            description='Run Series.',
            short_help='Run complicated series.',
            aliases=['series']
        )

    def run(self, pav_cfg, args):
        return 0