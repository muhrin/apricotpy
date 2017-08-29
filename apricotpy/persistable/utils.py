import importlib
import inspect
import uuid


class UuidMixin(object):
    def __init__(self, *args, **kwargs):
        super(UuidMixin, self).__init__(*args, **kwargs)
        self._uuid = uuid.uuid4()

    @property
    def uuid(self):
        return self._uuid


class ClassNotFoundException(Exception):
    pass


def fullname(obj):
    """
    Get the fully qualified name of an object.

    :param obj: The object to get the name from.
    :return: The fully qualified name.
    """
    if inspect.isclass(obj) or inspect.isfunction(obj):
        return obj.__module__ + "." + obj.__name__
    else:
        return obj.__module__ + "." + obj.__class__.__name__


def load_object(fullname):
    """
    Load a class from a string
    """
    class_data = fullname.split(".")
    module_path = ".".join(class_data[:-1])
    class_name = class_data[-1]

    module = importlib.import_module(module_path)

    # Finally, retrieve the class
    try:
        return getattr(module, class_name)
    except AttributeError:
        raise ClassNotFoundException("Class {} not found".format(fullname))


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
    obj.load_instance_state(saved_state, loop)
    return obj
