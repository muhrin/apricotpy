import importlib
import inspect


class ClassNotFoundException(Exception):
    pass


def fullname(obj):
    """
    Get the fully qualified name of an object.

    :param obj: The object to get the name from.
    :return: The fully qualified name.
    """
    if inspect.isclass(obj):
        return obj.__module__ + "." + obj.__name__
    else:
        return obj.__module__ + "." + obj.__class__.__name__


def load_class(classstring):
    """
    Load a class from a string
    """
    class_data = classstring.split(".")
    module_path = ".".join(class_data[:-1])
    class_name = class_data[-1]

    module = importlib.import_module(module_path)

    # Finally, retrieve the class
    try:
        return getattr(module, class_name)
    except AttributeError:
        raise ClassNotFoundException("Class {} not found".format(classstring))


class SimpleNamespace(object):
    """
    An attempt to emulate python 3's types.SimpleNamespace
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))

    def __eq__(self, other):
        return self.__dict__ == other.__dict__
