from pavilion.result_parsers import base_classes


class BadActivate(base_classes.ResultParser):

    def __init__(self):
        super().__init__(
            name='bad_activate',
            description="Fails upon activation.")

    def activate(self):
        raise ValueError("I'm supposed to happen too!")
