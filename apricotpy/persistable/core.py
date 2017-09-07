import abc
import inspect
import logging
import uuid
from . import utils

__all__ = ['LoopPersistable', 'Bundle', 'Unbundler']

_LOGGER = logging.getLogger(__name__)


class LoopPersistable(object):
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


class Bundle(dict):
    """
    This object represents the persisted state of a :class:`LoopPersistable` object.
    
    When instantiating it will ask the persistable to save its instance state
    which will trigger any child persistables to also be saved.
    """

    def __init__(self, persistable, bundles=None):
        super(Bundle, self).__init__()
        self._class_name = utils.class_name(persistable)
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
        if isinstance(value, LoopPersistable):
            self._ensure_bundle(value)
            return Reference(value)

        if utils.is_sequence_not_str(value):
            if isinstance(value, tuple):
                return tuple(self.encode(item) for item in value)
            else:
                raise ValueError("Unsupported sequence type ({}), use a tuple".format(type(value)))

        if isinstance(value, dict):
            return {k: self.encode(item) for k, item in value.iteritems()}

        if inspect.isfunction(value) or inspect.ismethod(value):
            from .persistables import Function

            fn_obj = Function(value)
            self._ensure_bundle(fn_obj)
            return Reference(fn_obj)

        if isinstance(value, (int, float, str, unicode, uuid.UUID)):
            return value

        if isinstance(value, BaseException):
            # TODO: Don't store exceptions directly!
            return value

        if value is None:
            return value

        raise ValueError("Unsupported value type '{}'".format(value))

    def _ensure_bundle(self, persistable):
        if id(persistable) not in self._bundles:
            self._bundles[id(persistable)] = Bundle(persistable, self._bundles)


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
        if isinstance(value, Reference):
            return self.get_persistable(value)

        if isinstance(value, tuple):
            return tuple(self.decode(item) for item in value)

        if isinstance(value, dict):
            return {k: self.decode(item) for k, item in value.iteritems()}

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
