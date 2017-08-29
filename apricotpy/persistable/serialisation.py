import abc
import os
import pickle
from . import core


class Persister(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def serialise_state(self, saved_state):
        pass

    @abc.abstractmethod
    def deserialise_state(self, uuid):
        """
        Load a state bundle from the UUID

        :param uuid: The object UUID
        :return: The state bundle
        :rtype: :class:`core.Bundle`
        """
        pass


def _ensure_directory(dir_path):
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)


class PicklePersister(Persister):
    def __init__(self, path):
        _ensure_directory(path)
        self._path = path

    def serialise_state(self, saved_state):
        uuid = saved_state[core.Persistable.UUID]
        path = os.path.join(self._path, "{}.p".format(uuid))
        with open(path, 'wb') as f:
            pickle.dump(saved_state, f)

    def deserialise_state(self, uuid):
        path = os.path.join(self._path, "{}.p".format(uuid))
        try:
            with open(path, 'rb') as f:
                return pickle.load(f)
        except pickle.UnpicklingError:
            raise ValueError("Unable to unpickle file '{}'".format(path))
