import abc
import collections
import inspect
import logging
from . import utils

__all__ = ['Bundle', 'Unbundler']

_LOGGER = logging.getLogger(__name__)


class Persistable(object):
    """
    An abstract class that defines objects that are persistable.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def loop(self):
        pass

    @abc.abstractmethod
    def save_instance_state(self, out_state):
        pass

    @abc.abstractmethod
    def load_instance_state(self, saved_state, loop):
        pass


class Reference(object):
    def __init__(self, obj):
        self.id = id(obj)


class CallbackDelegate(Persistable):
    OBJ = 'OBJ'
    FUNC_NAME = 'FUNC_NAME'

    def __init__(self, fn):

        if not inspect.isfunction(fn) and \
                not (inspect.ismethod(fn) and isinstance(fn.__self__, Persistable)):
            raise ValueError(
                "Callback must be a plain function or method of a persistable, got '{}'".format(fn)
            )

        self._fn = fn

    @property
    def fn(self):
        return self._fn

    def save_instance_state(self, out_state):
        super(CallbackDelegate, self).save_instance_state(out_state)
        if inspect.isfunction(self._fn):
            out_state[self.FUNC_NAME] = utils.fullname(self._fn)
        elif inspect.ismethod(self._fn):
            out_state[self.OBJ] = self._fn.__self__
            out_state[self.FUNC_NAME] = self._fn.__name__
        else:
            raise RuntimeError("Invalid state")

    def load_instance_state(self, saved_state, loop):
        super(CallbackDelegate, self).load_instance_state(saved_state, loop)

        try:
            obj = saved_state[self.OBJ]
            self._fn = getattr(obj, saved_state[self.FUNC_NAME])
        except KeyError:
            # Must be a plain function
            self._fn = utils.load_object(saved_state[self.FUNC_NAME])


_TYPE = '_TYPE'
_TYPE_CALLBACK = 'CALLBACK'
_CALLBACK_FN_NAME = 'CALLBACK_FN_NAME'
_CALLBACK_OBJ_ID = 'CALLBACK_OBJ_ID'


class Bundle(dict):
    """
    This object represents the persisted state of a :class:`Persistable` object.
    
    When instantiating it will ask the persistable to save its instance state
    which will trigger any child persistables to also be saved.
    """
    def __init__(self, persistable, bundles=None):
        super(Bundle, self).__init__()
        self._class_name = utils.fullname(persistable)
        self._id = id(persistable)

        if persistable.loop() is None:
            self._loop_id = None
        else:
            self._loop_id = id(persistable.loop())

        if bundles is None:
            # We're the 'root' bundle (i.e. the first to be Bundled)
            self._bundles = {}
            # 'Bootstrap' by inserting the root loop as empty
            if self._loop_id is not None:
                self._bundles[self._loop_id] = None
        else:
            assert self._id not in bundles, "Already bundled!"
            self._bundles = bundles

        self._bundles[id(persistable)] = self
        persistable.save_instance_state(self)

        _LOGGER.debug("Bundling {}".format(self))

    def __setitem__(self, key, value):
        if key in self:
            _LOGGER.warning(
                "Key '{}' already exists in the bundle for '{}', "
                "may be a unintentional conflict".format(key, self.class_name)
            )
        super(Bundle, self).__setitem__(key, self._transform(value))

    def __str__(self):
        return "{} ({})".format(self.class_name, self.id)

    @property
    def class_name(self):
        return self._class_name

    @property
    def id(self):
        return self._id

    @property
    def loop_id(self):
        return self._loop_id

    def set_loop(self, loop):
        if loop is not None:
            self._loop_id = id(loop)

    def unbundle(self, loop):
        """
        Create an object from a saved instance state into the given loop.

        :param loop: The event loop to load into
        :type loop: :class:`apricotpy.AbstractEventLoop`
        :return: An instance of the persitsable with its state loaded from this bundle.
        """
        _LOGGER.debug("Unbundling root {}".format(self))
        return Unbundler(self, loop).do()

    def _transform(self, value):
        if isinstance(value, Persistable):
            self._ensure_bundle(value)
            value = Reference(value)
        elif isinstance(value, (list, tuple)):
            value = [self._transform(item) for item in value]
        elif isinstance(value, collections.Mapping):
            value = {k: self._transform(item) for k, item in value.iteritems()}
        elif inspect.isfunction(value) or inspect.ismethod(value):
            value = self._save_callback(fn=value)

        return value

    def _ensure_bundle(self, persistable):
        if id(persistable) not in self._bundles:
            self._bundles[id(persistable)] = Bundle(persistable, self._bundles)

    def _save_callback(self, fn):
        out_state = {'_TYPE': _TYPE_CALLBACK}
        if inspect.isfunction(fn):
            out_state[_CALLBACK_FN_NAME] = utils.fullname(fn)
        elif inspect.ismethod(fn) and isinstance(fn.__self__, Persistable):
            out_state[_CALLBACK_OBJ_ID] = id(fn.__self__)
            out_state[_CALLBACK_FN_NAME] = fn.__name__
        else:
            raise ValueError(
                "Must supply a function or persistable object method. "
                "Got '{}'".format(fn)
            )

        return out_state


class Unbundler(object):
    """
    The unbundler provides a readonly view of a bundle that is used while a 
    persistable is reloading its state.
    """

    def __init__(self, bundle, loop, persistables=None):
        self._bundle = bundle
        self._unbundled = None

        if persistables is None:
            # We're the root that is being unbundled
            self._persistables = {}
            if self._bundle.loop_id is not None:
                self._persistables[self._bundle.loop_id] = loop
        else:
            self._persistables = persistables
            ref_id = bundle.id
            if ref_id in self._persistables:
                self._unbundled = self._persistables[ref_id]

    def do(self):
        if self._unbundled is None:
            _LOGGER.debug("Unbundling {}".format(self._bundle))

            # Get the class using the class loader and instantiate it
            persistable_class = utils.load_object(self._bundle.class_name)
            persistable = persistable_class.__new__(persistable_class)

            # Have to put it in the persistables dictionary here as it may be accessed
            # in load_instance_state
            self._persistables[self._bundle.id] = persistable

            persistable.load_instance_state(self, self._get_loop(self._bundle.loop_id))

            if isinstance(persistable, CallbackDelegate):
                self._unbundled = persistable.fn
            else:
                self._unbundled = persistable

            _LOGGER.debug("Unbundled {}".format(self._bundle))

        return self._unbundled

    def __getitem__(self, item):
        return self._transform(self._bundle[item])

    def loop(self):
        return self._get_loop(self._bundle.loop_id)

    def _transform(self, value):
        if isinstance(value, Reference):
            value = self._get_persistable(value.id)
        elif isinstance(value, (list, tuple)):
            value = [self._transform(item) for item in value]
        elif isinstance(value, collections.Mapping):
            if _TYPE in value and value[_TYPE] == _TYPE_CALLBACK:
                value = self._load_callback(value)
            else:
                # Just a plain mapping
                value = {k: self._transform(item) for k, item in value.iteritems()}

        return value

    def _get_persistable(self, ref_id):
        if ref_id in self._persistables:
            return self._persistables[ref_id]
        else:
            bundle = self._bundle._bundles[ref_id]
            loop = self._get_loop(bundle.loop_id)

            persistable = Unbundler(bundle, loop, self._persistables).do()
            self._persistables[ref_id] = persistable

            return persistable

    def _get_loop(self, loop_id):
        if loop_id is not None:
            return self._get_persistable(loop_id)
        else:
            return None

    def _load_callback(self, saved_state):
        obj_id = saved_state.get(_CALLBACK_OBJ_ID, None)
        if obj_id is not None:
            obj = self._get_persistable(obj_id)
            return getattr(obj, saved_state[_CALLBACK_FN_NAME])
        else:
            return utils.load_object(saved_state[_CALLBACK_FN_NAME])
