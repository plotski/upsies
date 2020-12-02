try:
    from functools import cached_property as property
except ImportError:
    import functools

    # https://github.com/jackmaney/lazy-property/
    class property():
        """Property that replaces itself with its return value on first access"""

        def __init__(self, fget):
            self.fget = fget
            functools.update_wrapper(self, fget)
            self.fset = None

        def __get__(self, obj, cls):
            if obj is None:
                return self
            else:
                value = self.fget(obj)
                setattr(obj, self.fget.__name__, value)
                return value
