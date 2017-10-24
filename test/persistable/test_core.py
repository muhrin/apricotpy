import apricotpy.utils
from . import utils
import apricotpy.persistable as persistable


class PersistableObj(persistable.LoopPersistable):
    def __init__(self, value):
        self.store.value = value


class TestLoopPersistable(utils.TestCaseWithLoop):
    def test_store_simple(self):
        p = PersistableObj(5)
        saved_state = persistable.Bundle(p)
        del p

        p = saved_state.unbundle()
        self.assertEqual(p.store.value, 5)

    def test_store_advanced(self):
        for value in [
            persistable.LoopPersistable(),
            [persistable.LoopPersistable()],
            {'value': persistable.LoopPersistable()}
        ]:
            p = PersistableObj(value)
            saved_state = persistable.Bundle(p)
            del p

            p = saved_state.unbundle()
            self.assertEqual(p.store.value, value)

    def test_store_incorrect_type(self):
        with self.assertRaises(TypeError):
            p = PersistableObj((1, 2))
