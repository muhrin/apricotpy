import logging

import apricotpy.utils
from . import core
from . import utils

__all__ = ['ContextMixin']

_LOGGER = logging.getLogger(__name__)


class ContextMixin(object):
    """
    Add a context to a LoopPersistable.  The contents of the context will be saved
    in the instance state unlike standard instance variables.
    """
    CONTEXT = 'context'

    def __init__(self, *args, **kwargs):
        assert isinstance(self, core.LoopPersistable), "Has to be used with a LoopPersistable"

        super(ContextMixin, self).__init__(*args, **kwargs)
        self._context = apricotpy.utils.AttributesDict()

    @property
    def ctx(self):
        return self._context

    def save_instance_state(self, out_state):
        super(ContextMixin, self).save_instance_state(out_state)

        out_state[self.CONTEXT] = self._context.__dict__

    def load_instance_state(self, saved_state):
        super(ContextMixin, self).load_instance_state(saved_state)

        self._context = apricotpy.utils.SimpleNamespace(**saved_state[self.CONTEXT])
