import apricotpy
from . import futures
from . import objects

__all__ = ['AwaitableLoopObject']


class MakeAwaitableMixinPersistable(object):
    """
    Take a :class:`apricotpy.AwaitableMixin` and make it :class:`core.LoopPersistable`
    """
    FUTURE = 'FUTURE'

    def __init__(self, *args, **kwargs):
        assert isinstance(self, apricotpy.AwaitableMixin), \
            "Has to be used with an AwaitableMixin"
        super(MakeAwaitableMixinPersistable, self).__init__(*args, **kwargs)
        self._future = futures.Future(loop=kwargs.get('loop', None))

    def save_instance_state(self, out_state):
        super(MakeAwaitableMixinPersistable, self).save_instance_state(out_state)

        out_state[self.FUTURE] = self._future

    def load_instance_state(self, saved_state):
        super(MakeAwaitableMixinPersistable, self).load_instance_state(saved_state)

        self._future = saved_state[self.FUTURE]


class AwaitableMixin(MakeAwaitableMixinPersistable, apricotpy.AwaitableMixin):
    pass


class AwaitableLoopObject(
    AwaitableMixin,
    objects.LoopObject):  # Start as a persistable LoopObject
    """
    A convenience class that gives a LoopObject that is both LoopPersistable and
    Awaitable.
    
    The user should overwrite `save/load_instance_state()` appropriately,
    remembering to call `super()`
    """
    pass
