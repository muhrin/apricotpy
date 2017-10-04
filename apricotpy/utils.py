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


class AttributesDict(SimpleNamespace):
    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, item):
        return getattr(self, item)

    def setdefault(self, key, value):
        return self.__dict__.setdefault(key, value)

    def get(self, *args, **kwargs):
        return self.__dict__.get(*args, **kwargs)
