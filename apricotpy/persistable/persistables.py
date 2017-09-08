import inspect
from . import core
from . import utils

__all__ = ['Function']

_FN = 'FN'
_ARGS = 'ARGS'
_KWARGS = 'KWARGS'


class Function(core.LoopPersistable):
    def __init__(self, fn, *args, **kwargs):
        if not inspect.isfunction(fn) and not inspect.ismethod(fn):
            raise ValueError("fn must be a function")

        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def loop(self):
        # Don't need a loop
        return None

    def save_instance_state(self, out_state):
        super(Function, self).save_instance_state(out_state)

        out_state[_FN] = utils.function_name(self._fn)

        # If method, store self as an argument
        if inspect.ismethod(self._fn):
            out_state[_ARGS] = (self._fn.__self__,) + self._args
        else:
            out_state[_ARGS] = self._args

        out_state[_KWARGS] = self._kwargs

    def load_instance_state(self, saved_state):
        super(Function, self).load_instance_state(saved_state)

        self._fn = utils.load_object(saved_state[_FN])

        # If method, bind back the instance class
        args = saved_state[_ARGS]
        if inspect.ismethod(self._fn):
            obj = args[0]
            self._fn = self._fn.__get__(obj, obj.__class__)
            self._args = args[1:]
        else:
            self._args = args

        self._kwargs = saved_state[_KWARGS]

    def __call__(self, *args, **kwargs):
        args = self._args + args
        kwargs = dict(self._kwargs)
        kwargs.update(kwargs)

        return self._fn(*args, **kwargs)
