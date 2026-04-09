import threading
from typing import Type

class Singleton(type):
    """
    Create a class which only init once
    Instruction:
        class foo(metaclass=Singleton)
    """
    _instance = {}
    _lock = threading.Lock()
    def __call__(cls, *args, **kwds):
        if cls not in cls._instance:
            with cls._lock:
                if cls not in cls._instance:
                    instance = super().__call__(*args, **kwds)
                    cls._instance[cls] = instance
        return cls._instance[cls]
