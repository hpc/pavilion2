from pavilion.result import parsers


class BadActivate(parsers.ResultParser):

    def __init__(self):
        super().__init__(
            name='bad_activate',
            description="Fails upon activation.")

    def activate(self):
        raise ValueError("I'm supposed to happen too!")
