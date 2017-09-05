import abc
import inspect
import logging
import uuid
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


class Custom(object):
    def __init__(self, type_id, value):
        self.type_id = type_id
        self.value = value


class PersistablePersister(object):
    @staticmethod
    def encode(persistable, bundler):
        if not isinstance(persistable, Persistable):
            raise TypeError

        bundler._ensure_bundle(persistable)
        return Reference(persistable)

    @staticmethod
    def decode(reference, unbundler):
        if not isinstance(reference, Reference):
            raise TypeError

        return unbundler.get_persistable(reference)


class ListPersister(object):
    @staticmethod
    def encode(list_, bundler):
        if not isinstance(list_, tuple):
            raise TypeError

        return tuple(bundler.encode(item) for item in list_)

    @staticmethod
    def decode(list_, unbundler):
        if not isinstance(list_, tuple):
            raise TypeError

        return tuple(unbundler.decode(item) for item in list_)


class DictPersister(object):
    @staticmethod
    def encode(dict_, bundler):
        if not isinstance(dict_, dict):
            raise TypeError

        return {k: bundler.encode(item) for k, item in dict_.iteritems()}

    @staticmethod
    def decode(dict_, unbundler):
        if not isinstance(dict_, dict):
            raise TypeError

        return {k: unbundler.decode(item) for k, item in dict_.iteritems()}


class CallbackPersister(object):
    TYPE_ID = '88356b3e-4596-46b2-a223-c3a78d20cdb2'

    @classmethod
    def encode(cls, fn, bundler):
        if inspect.isfunction(fn):
            encoded = utils.fullname(fn)
        elif inspect.ismethod(fn) and isinstance(fn.__self__, Persistable):
            encoded = (Reference(fn.__self__), fn.__name__)
        else:
            raise TypeError(
                "Must supply a function or persistable object method. "
                "Got '{}'".format(fn)
            )

        return Custom(cls.TYPE_ID, encoded)

    @classmethod
    def decode(cls, encoded, unbundler):
        if not (isinstance(encoded, Custom) and encoded.type_id == cls.TYPE_ID):
            raise ValueError("Not a callback type")

        try:
            # Maybe it's a method in which case the value is a tuple
            obj = unbundler.get_persistable(encoded.value[0])
            return getattr(obj, encoded.value[1])
        except TypeError:
            # It should be a function name then
            return utils.load_object(encoded.value)


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

    ENCODERS = (PersistablePersister.encode,
                ListPersister.encode,
                DictPersister.encode,
                CallbackPersister.encode)

    def __init__(self, persistable, bundles=None):
        super(Bundle, self).__init__()
        self._class_name = utils.fullname(persistable)
        self._id = id(persistable)

        if persistable.loop() is None:
            self._loop_ref = None
        else:
            self._loop_ref = Reference(persistable.loop())

        if bundles is None:
            # We're the 'root' bundle (i.e. the first to be Bundled)
            self._bundles = {}
            # 'Bootstrap' by inserting the root loop as empty
            if self._loop_ref is not None:
                self._bundles[self._loop_ref.id] = None
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

        value = self.encode(value)
        super(Bundle, self).__setitem__(key, value)

    def __str__(self):
        return "{} ({})".format(self.class_name, self.id)

    @property
    def class_name(self):
        return self._class_name

    @property
    def id(self):
        return self._id

    @property
    def loop_ref(self):
        return self._loop_ref

    def unbundle(self, loop):
        """
        Create an object from a saved instance state into the given loop.

        :param loop: The event loop to load into
        :type loop: :class:`apricotpy.AbstractEventLoop`
        :return: An instance of the persitsable with its state loaded from this bundle.
        """
        _LOGGER.debug("Unbundling root {}".format(self))
        return Unbundler(self, loop).do()

    def encode(self, value):
        for encode in self.ENCODERS:
            try:
                value = encode(value, self)
                break
            except (TypeError, ValueError):
                pass

        self._check_value(value)
        return value

    def _ensure_bundle(self, persistable):
        if id(persistable) not in self._bundles:
            self._bundles[id(persistable)] = Bundle(persistable, self._bundles)

    def _check_value(self, value):
        if isinstance(value, Reference):
            return
        if isinstance(value, tuple):
            for item in value:
                self._check_value(item)
            return
        if isinstance(value, dict):
            for item in value.itervalues():
                self._check_value(item)
            return
        if isinstance(value, Custom):
            return
        if isinstance(value, (int, float, str, unicode, uuid.UUID)):
            return
        if value is None:
            return
        if isinstance(value, BaseException):
            return

        raise RuntimeError("Invalid type '{}'".format(value))


class Unbundler(object):
    """
    The unbundler provides a readonly view of a bundle that is used while a 
    persistable is reloading its state.
    """

    DECODERS = (PersistablePersister.decode,
                ListPersister.decode,
                DictPersister.decode,
                CallbackPersister.decode)

    def __init__(self, bundle, loop, persistables=None):
        self._bundle = bundle
        self._unbundled = None

        if persistables is None:
            # We're the root that is being unbundled
            self._persistables = {}
            if self._bundle.loop_ref is not None:
                self._persistables[self._bundle.loop_ref.id] = loop
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

            persistable.load_instance_state(self, self._get_loop(self._bundle.loop_ref))

            self._unbundled = persistable
            _LOGGER.debug("Unbundled {}".format(self._bundle))

        return self._unbundled

    def __getitem__(self, item):
        return self.decode(self._bundle[item])

    def loop(self):
        return self._get_loop(self._bundle.loop_ref)

    def decode(self, value):
        for decode in self.DECODERS:
            try:
                value = decode(value, self)
                break
            except (TypeError, ValueError):
                pass

        return value

    def get_persistable(self, ref):
        if not isinstance(ref, Reference):
            raise TypeError

        if ref.id in self._persistables:
            return self._persistables[ref.id]
        else:
            bundle = self._bundle._bundles[ref.id]
            loop = self._get_loop(bundle.loop_ref)

            persistable = Unbundler(bundle, loop, self._persistables).do()
            self._persistables[ref.id] = persistable

            return persistable

    def _get_loop(self, ref):
        if ref is not None:
            return self.get_persistable(ref)
        else:
            return None

    def _load_callback(self, saved_state):
        obj_id = saved_state.get(_CALLBACK_OBJ_ID, None)
        if obj_id is not None:
            obj = self.get_persistable(obj_id)
            return getattr(obj, saved_state[_CALLBACK_FN_NAME])
        else:
            return utils.load_object(saved_state[_CALLBACK_FN_NAME])
