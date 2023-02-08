from pavilion import module_wrapper
from pavilion.module_actions import ModuleLoad


class ModuleWrapperTest(module_wrapper.ModuleWrapper):

    def __init__(self):
        super().__init__('itsa', "")

    def load(self, sys_info, name, requested_version=None):

        del sys_info

        return [ModuleLoad('fake')], {'FAKE_VAR': "Itsa_real"}
