import logging
from abc import ABCMeta, abstractmethod

from . import futures
from . import tasks
from . import objects
from . import utils

__all__ = ['Persistable',
           'PersistableAwaitableLoopObject',
           'PersistableLoopObject',
           'PersistableLoopObjectMixin',
           'PersistableAwaitableMixin',
           'PersistableTask',
           'ContextMixin',
           'persistable_object_factory',
           'Bundle']

_LOGGER = logging.getLogger(__name__)

Bundle = dict


class Persistable(object):
    """
    An abstract class that defines objects that are persistable.
    """
    __metaclass__ = ABCMeta

    CLASS_NAME = 'class_name'

    @classmethod
    def create_from(cls, loop, saved_state, *args):
        """
        Create an object from a saved instance state.

        :param loop: The event loop
        :type loop: :class:`apricotpy.AbstractEventLoop`
        :param saved_state: The saved state
        :type saved_state: :class:`Bundle`
        :return: An instance of this task with its state loaded from the save state.
        """
        # Get the class using the class loader and instantiate it
        class_name = saved_state[cls.CLASS_NAME]
        my_name = utils.fullname(cls)
        if class_name != my_name:
            _LOGGER.warning(
                "Loading class from a bundle that was created from a class with a different "
                "name.  This class is '{}', bundle created by '{}'".format(class_name, my_name))

        task = cls.__new__(cls)
        task.load_instance_state(loop, saved_state, *args)
        return task

    def save_instance_state(self, out_state):
        out_state[self.CLASS_NAME] = utils.fullname(self)

    @abstractmethod
    def load_instance_state(self, loop, saved_state, *args):
        pass


def load_from(loop, saved_state, *args):
    # Get the class using the class loader and instantiate it
    class_name = saved_state[Persistable.CLASS_NAME]
    task_class = utils.load_class(class_name)
    return loop.create(task_class, saved_state, *args)


class PersistableLoopObjectMixin(Persistable):
    """
    A mixin that makes a :class:`objects.LoopObject` :class:`Persistable`.
      
    Because this is a mixin in can be inserted an any point in the inheritance hierarchy.
    """
    UUID = 'uuid'

    def __init__(self, *args, **kwargs):
        assert isinstance(self, objects.LoopObject), "Has to be used with a LoopObject"
        super(PersistableLoopObjectMixin, self).__init__(*args, **kwargs)

    def save_instance_state(self, out_state):
        super(PersistableLoopObjectMixin, self).save_instance_state(out_state)
        out_state[self.UUID] = self.uuid

    def load_instance_state(self, loop, saved_state, *args):
        super(PersistableLoopObjectMixin, self).load_instance_state(loop, saved_state, *args)
        self._loop = loop
        self._uuid = saved_state[self.UUID]


class PersistableLoopObject(PersistableLoopObjectMixin, objects.LoopObject):
    """
    A convenience to get a LoopObject that is Persistable.  
    
    The user should overwrite `save/load_instance_state()` appropriately,
    remembering to call `super()`
    """
    pass


class PersistableAwaitableMixin(Persistable):
    """
    A mixin that makes an :class:`futures.Awaitable` :class:`Persistable`
    
    ..warning:: Callbacks are not (and in general cannot) be persisted.
    """

    RESULT = 'RESULT'
    EXCEPTION = 'EXCEPTION'
    CANCELLED = 'CANCELLED'

    def __init__(self, *args, **kwargs):
        assert isinstance(self, futures.Awaitable), "Has to be used with an Awaitable"
        assert isinstance(self, objects.LoopObject), "Has to be used with a LoopObject"
        super(PersistableAwaitableMixin, self).__init__(*args, **kwargs)
        self.__saved_state = None

    def save_instance_state(self, out_state):
        super(PersistableAwaitableMixin, self).save_instance_state(out_state)

        if self.done():
            try:
                out_state[self.RESULT] = self.result()
            except futures.CancelledError:
                out_state[self.CANCELLED] = True
            except BaseException as e:
                out_state[self.EXCEPTION] = e

    def load_instance_state(self, loop, saved_state, *args):
        super(PersistableAwaitableMixin, self).load_instance_state(loop, saved_state, *args)
        self._future = futures.Future(None)
        # We want to set the state of the Awaitable here but can't because
        # you can't call any of the setters before loop insertion so save
        # the state until on_loop_inserted()
        self.__saved_state = saved_state

    def on_loop_inserted(self, loop):
        super(PersistableAwaitableMixin, self).on_loop_inserted(loop)

        if self.__saved_state is not None:
            try:
                self.set_result(self.__saved_state[self.RESULT])
            except KeyError:
                try:
                    self.set_exception(self.__saved_state[self.EXCEPTION])
                except KeyError:
                    try:
                        if self.__saved_state[self.CANCELLED]:
                            self.cancel()
                    except KeyError:
                        pass

            self.__saved_state = None


class PersistableAwaitableLoopObject(
    PersistableAwaitableMixin, objects.AwaitableMixin, PersistableLoopObject):
    """
    A convenience class that gives a LoopObject that is both Persistable and
    Awaitable.
    
    The user should overwrite `save/load_instance_state()` appropriately,
    remembering to call `super()`
    """
    pass


class ContextMixin(object):
    """
    Add a context to a Persistable.  The contents of the context will be saved
    in the instance state unlike standard instance variables.
    """
    CONTEXT = 'context'

    def __init__(self, *args, **kwargs):
        assert isinstance(self, Persistable), "Has to be used with a Persistable"

        super(ContextMixin, self).__init__(*args, **kwargs)
        self._context = utils.SimpleNamespace()

    @property
    def ctx(self):
        return self._context

    def save_instance_state(self, out_state):
        super(ContextMixin, self).save_instance_state(out_state)
        out_state[self.CONTEXT] = Bundle(self._context.__dict__)

    def load_instance_state(self, loop, saved_state, *args):
        super(ContextMixin, self).load_instance_state(loop, saved_state, *args)
        self._context = utils.SimpleNamespace(**saved_state[self.CONTEXT])


class PersistableTask(
    PersistableAwaitableMixin, PersistableLoopObjectMixin, tasks.Task):
    __metaclass__ = ABCMeta

    AWAITING = 'AWAITING'
    AWAITING_RESULT = 'AWAITING_RESULT'
    CALLBACK = 'CALLBACK'
    DIRECTIVE = 'DIRECTIVE'

    def __init__(self, loop):
        super(PersistableTask, self).__init__(loop)
        self.__saved_state = None

    def save_instance_state(self, out_state):
        super(PersistableTask, self).save_instance_state(out_state)

        out_state[self.DIRECTIVE] = self._directive
        if self._directive == tasks.Await.__name__:

            # Do we have the result already?
            if self._awaiting_result is not tasks._NO_RESULT:
                out_state[self.AWAITING_RESULT] = self._awaiting_result
            else:
                awaiting = self.awaiting()
                try:
                    bundle = Bundle()
                    awaiting.save_instance_state(bundle)
                    out_state[self.AWAITING] = bundle
                except AttributeError:
                    raise RuntimeError("Awaitable is not persistable: '{}".format(awaiting.__class__))

            out_state[self.CALLBACK] = self._callback.__name__

        elif self._directive == tasks.Continue.__name__:
            out_state[self.CALLBACK] = self._callback.__name__

    def load_instance_state(self, loop, saved_state, *args):
        super(PersistableTask, self).load_instance_state(loop, saved_state, *args)
        # have to hold back the saved state until we're inserted
        self.__saved_state = saved_state

        self._directive = None
        self._awaiting = None
        self._callback = None
        self._awaiting_result = tasks._NO_RESULT

        self._paused = False
        self._callback_handle = None

    def on_loop_inserted(self, loop):
        # Do this before calling super() so the superclass has the right state
        if self.__saved_state is not None:
            saved_state = self.__saved_state
            self.__saved_state = None

            self._directive = saved_state[self.DIRECTIVE]
            if self._directive == tasks.Await.__name__:
                # Do we have the result already?
                try:
                    self._awaiting_result = saved_state[self.AWAITING_RESULT]
                except KeyError:
                    self._awaiting = load_from(self.loop(), saved_state[self.AWAITING])
                self._callback = getattr(self, saved_state[self.CALLBACK])
            elif self._directive == tasks.Continue.__name__:
                self._callback = getattr(self, saved_state[self.CALLBACK])

        super(PersistableTask, self).on_loop_inserted(loop)


def persistable_object_factory(loop, obj_class, *args, **kwargs):
    if isinstance(obj_class, Bundle):
        # User just passed in a Bundle and the bundle should contain the class
        return load_from(loop, obj_class, *args)
    elif args and len(args) == 1 and isinstance(args[0], Bundle):
        if kwargs:
            RuntimeError("Found unexpected kwargs in call to process factory")
        return obj_class.create_from(loop, args[0])
    elif kwargs and 'saved_state' in kwargs:
        return obj_class.create_from(loop, kwargs['saved_state'])
    else:
        try:
            return obj_class(loop, *args, **kwargs)
        except TypeError as e:
            raise TypeError("Failed to create '{}', {}".format(obj_class, e.message))
