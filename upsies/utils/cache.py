import functools

# https://github.com/jackmaney/lazy-property/

class property:
    """Property that is only computed once per instance"""

    def __init__(self, fget):
        self.fget = fget
        functools.update_wrapper(self, fget)
        self.fset = None

    @property
    def setter(self):
        def setter(fset):
            self.fset = fset
            functools.update_wrapper(self, fset)
        return setter

    def __get__(self, obj, cls):
        if obj is None:
            return self
        else:
            value = self.fget(obj)
            setattr(obj, self.fget.__name__, value)
            return value
