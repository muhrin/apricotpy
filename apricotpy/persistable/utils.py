import collections
from collections import deque
import importlib
import inspect
import uuid

from past.builtins import basestring

class UuidMixin(object):
    def __init__(self, *args, **kwargs):
        super(UuidMixin, self).__init__(*args, **kwargs)
        self._uuid = uuid.uuid4()

    @property
    def uuid(self):
        return self._uuid


class ClassNotFoundException(Exception):
    pass


class ClassLoader(object):
    def __init__(self, parent=None):
        self._parent = parent

    def find_class(self, name):
        """
        Load a class from a string
        """
        return load_object(name)

    def load_class(self, name):
        # Try the parent first
        if self._parent is not None:
            Class = self._parent.find_class(name)
            if Class is not None:
                return Class

        return self.find_class(name)


def function_name(fn):
    try:
        name = fn.__module__ + '.' + fn.__qualname__
    except AttributeError:
        if inspect.ismethod(fn):
            cls = fn.__self__.__class__
            name = class_name(cls) + '.' + fn.__name__
        elif inspect.isfunction(fn):
            name = fn.__module__ + '.' + fn.__name__
        else:
            raise ValueError("Must be function or method")

    # Make sure we can load it
    try:
        load_object(name)
    except ValueError:
        raise ValueError("Could not create a consistent name for fn '{}'".format(fn))

    return name


def load_function(name, instance=None):
    obj = load_object(name)
    if inspect.ismethod(obj):
        if instance is not None:
            return obj.__get__(instance, instance.__class__)
        else:
            return obj
    elif inspect.isfunction(obj):
        return obj
    else:
        raise ValueError("Invalid function name '{}'".format(name))


def class_name(obj, class_loader=None):
    """
    Given a class or an instance this function will give the fully qualified name
    e.g. 'my_module.MyClass'

    :param obj: The object to get the name from.
    :return: The fully qualified name.
    """

    if not inspect.isclass(obj):
        # assume it's an instance
        obj = obj.__class__

    name = obj.__module__ + '.' + obj.__name__

    try:
        if class_loader is not None:
            class_loader.load_class(name)
        else:
            load_object(name)
    except ValueError:
        raise ValueError("Could not create a consistent full name for object '{}'".format(obj))

    return name


def load_object(fullname):
    """
    Load a class from a string
    """
    obj, remainder = load_module(fullname)

    # Finally, retrieve the object
    for name in remainder:
        try:
            obj = getattr(obj, name)
        except AttributeError:
            raise ValueError("Could not load object corresponding to '{}'".format(fullname))

    return obj


def load_module(fullname):
    parts = fullname.split('.')

    # Try to find the module, working our way from the back
    mod = None
    remainder = deque()
    for i in range(len(parts)):
        try:
            mod = importlib.import_module('.'.join(parts))
            break
        except ImportError:
            remainder.appendleft(parts.pop())

    if mod is None:
        raise ValueError("Could not load a module corresponding to '{}'".format(fullname))

    return mod, remainder


def create_from_with_loop(saved_state, loop):
    """
    Create an object from the saved state providing a loop to load_instance_state()

    :param saved_state: The saved state
    :type saved_state: :class:`Bundle`
    :param loop: The event loop
    :return: An instance of the object with its state loaded from the save state.
    """
    # Get the class using the class loader and instantiate it
    class_name = saved_state['CLASS_NAME']
    obj_class = load_object(class_name)
    obj = obj_class.__new__(obj_class)
    obj.load_instance_state(saved_state)
    return obj


def is_sequence_not_str(value):
    """
    A helper to check if a value is of type :class:`collections.Sequence`
    but not a string type (i.e. :class:`str` or :class:`unicode`)

    :param value: The value to check
    :return: True of a sequence but not string, False otherwise
    :rtype: bool
    """
    return isinstance(value, collections.Sequence) and \
           not isinstance(value, basestring)
