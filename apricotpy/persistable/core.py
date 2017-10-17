import abc
import apricotpy
import collections
import inspect
import logging
import uuid

from past.builtins import basestring
from future.utils import with_metaclass

from . import utils

__all__ = ['LoopPersistable', 'Bundle', 'Unbundler']

_LOGGER = logging.getLogger(__name__)
_NULL = tuple()
_KEY_CLASS_LOADER = 'class_loader'


class LoopPersistable(with_metaclass(abc.ABCMeta, object)):
    """
    An abstract class that defines objects that are persistable.
    """

    # Class variables serving as defaults for instance variables.
    _persistable_id = None

    @property
    def persistable_id(self):
        """
        Overwrite this if you want to provide your own persistable ID, e.g.
        because you already have a UUID.

        Be careful though, this ID should be a unique type that identifies this
        _instance_!  And must be of a type that can be saved in :class:`Bundle`

        :return: A persistable id that identifies this instance
        """
        if self._persistable_id is None:
            self._persistable_id = uuid.uuid4()
        return self._persistable_id

    def loop(self):
        return None

    @abc.abstractmethod
    def save_instance_state(self, out_state):
        pass

    @abc.abstractmethod
    def load_instance_state(self, saved_state):
        pass


class _Reference(collections.Hashable):
    def __init__(self, obj):
        assert isinstance(obj, LoopPersistable), \
            "Can only refer to loop persistables, got '{}".format(obj)
        self.id = obj.persistable_id

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other

    def __repr__(self):
        return "<Reference {}>".format(self.id)


class Bundle(dict):
    """
    This object represents the persisted state of a :class:`LoopPersistable` object.

    When instantiating it will ask the persistable to save its instance state
    which will trigger any child persistables to also be saved.
    """

    def __init__(self, persistable, class_loader=None, root=None):
        super(Bundle, self).__init__()
        self.set_class_loader(class_loader)
        self._class_name = utils.class_name(persistable, class_loader)
        self._id = _Reference(persistable)

        if persistable.loop() is None:
            self._loop_ref = None
        else:
            self._loop_ref = _Reference(persistable.loop())

        if root is None:
            # We're the 'root' bundle (i.e. the first to be Bundled)
            self._root = self
            self._bundles = {}
            # 'Bootstrap' by inserting the root loop as empty
            if self._loop_ref is not None:
                self._bundles[self._loop_ref] = None
        else:
            assert self._id not in root._bundles, "Already bundled!"
            self._root = root

        self._root._bundles[_Reference(persistable)] = self
        persistable.save_instance_state(self)

        _LOGGER.debug("Bundling {}".format(self))

    def __getitem__(self, item):
        return super(Bundle, self).__getitem__(item)

    def __setitem__(self, key, value):
        if key in self:
            _LOGGER.warning(
                "Key '{}' already exists in the bundle for '{}', "
                "may be a unintentional conflict".format(key, self.class_name)
            )

        value = self._encode(value)
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
        """
        The reference to the loop this persistable is in
        """
        return self._loop_ref

    def set_class_loader(self, class_loader):
        self._class_loader = class_loader

    def unbundle(self, loop):
        """
        Create an object from a saved instance state into the given loop.

        :param loop: The event loop to load into
        :type loop: :class:`apricotpy.AbstractEventLoop`
        :return: An instance of the persitsable with its state loaded from this bundle.
        """
        _LOGGER.debug("Unbundling root {}".format(self))
        return Unbundler(self, loop).do()

    def _encode(self, value):
        if isinstance(value, apricotpy.LoopObject) and \
                not isinstance(value, LoopPersistable):
            raise ValueError("The object '{}' is not persistable".format(value))

        if isinstance(value, LoopPersistable):
            return self._ensure_bundle(value)

        if utils.is_sequence_not_str(value):
            if isinstance(value, tuple):
                return tuple(self._encode(item) for item in value)
            else:
                raise ValueError("Unsupported sequence type ({}), use a tuple".format(type(value)))

        if isinstance(value, dict):
            return {k: self._encode(item) for k, item in value.items()}

        if inspect.isfunction(value) or inspect.ismethod(value):
            from .persistables import Function

            fn_obj = Function(value)
            return self._ensure_bundle(fn_obj)

        if isinstance(value, (int, float, basestring, uuid.UUID)):
            return value

        if isinstance(value, BaseException):
            # TODO: Don't store exceptions directly!
            return value

        if value is None:
            return value

        raise ValueError("Unsupported value type '{}'".format(value))

    def _ensure_bundle(self, persistable):
        ref = _Reference(persistable)
        try:
            self._get_bundle(ref)
        except ValueError:
            self._root._bundles[ref] = Bundle(persistable, root=self._root)
        return ref

    def _get_bundle(self, ref):
        try:
            return self._root._bundles[ref]
        except KeyError:
            raise ValueError("Reference ({}) to bundle not found".format(ref))

    def _load_class(self, cls):
        if self._root._class_loader is not None:
            return self._class_loader.load_class(cls)
        else:
            return utils.load_object(cls)



class Unbundler(collections.Mapping):
    """
    The unbundler provides a readonly view of a bundle that is used while a
    persistable is reloading its state.
    """

    def __init__(self, bundle, loop=None, persistables=None):
        self._bundle = bundle
        self._unbundled = None

        # Adopt lazy-unbundling approach.  Nothing actually gets loaded
        # here, only when it is requested via the do() call

        if persistables is None:
            # We're the root that is being unbundled
            self._persistables = {}
            if self.loop_ref is not None:
                self._persistables[self.loop_ref] = loop
        else:
            # A parent unbundler passed us the global persistables
            self._persistables = persistables
            ref_id = bundle.id
            if ref_id in self._persistables:
                self._unbundled = self._persistables[ref_id]

    def do(self):
        if self._unbundled is None:
            _LOGGER.debug("Unbundling {}".format(self._bundle))

            # Get the class using the class loader and instantiate it
            persistable_class = self._bundle._load_class(self._bundle.class_name)
            persistable = persistable_class.__new__(persistable_class)

            # Have to put it in the persistables dictionary here as it may be accessed
            # in load_instance_state during loading
            self._persistables[self._bundle.id] = persistable

            persistable.load_instance_state(self)

            self._unbundled = persistable
            _LOGGER.debug("Unbundled {}".format(self._bundle))

        return self._unbundled

    def __iter__(self):
        return self._bundle.__iter__()

    def __len__(self):
        return self._bundle.__len__()

    def __getitem__(self, item):
        return self.decode(self._bundle[item])

    def __contains__(self, item):
        return self._bundle.__contains__(item)

    @property
    def loop_ref(self):
        return self._bundle.loop_ref

    def get(self, item, default=_NULL):
        try:
            self.__getitem__(item)
        except KeyError:
            if default is not _NULL:
                return default
            else:
                raise ValueError("Unknown item")

    def loop(self):
        if self.loop_ref is not None:
            return self.get_persistable(self.loop_ref)
        else:
            return None

    def decode(self, value):
        if isinstance(value, _Reference):
            return self.get_persistable(value)

        if isinstance(value, tuple):
            return tuple(self.decode(item) for item in value)

        if isinstance(value, dict):
            return {k: self.decode(item) for k, item in value.items()}

        return value

    def get_persistable(self, ref):
        if not isinstance(ref, _Reference):
            raise TypeError

        bundle = self._bundle._get_bundle(ref)

        if ref in self._persistables:
            return self._persistables[ref]
        else:
            persistable = Unbundler(bundle, persistables=self._persistables).do()
            self._persistables[ref] = persistable
            return persistable
