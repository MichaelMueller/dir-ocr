import abc
import os
from old.DataStructures import *


class Functor:
    @abc.abstractmethod
    def __call__(self):
        pass


class FilePathsFromDirectory(Functor):
    def __init__(self):
        self.directory = None  # type: Scalar
        self.extensions = None  # type: Array
        self.file_paths = None  # type: Array

    def __call__(self):
        for root, dirs, files in os.walk(self.directory.val):
            for basename in files:
                file_name, ext = os.path.splitext(basename)
                ext = ext[1:].lower()
                if self.extensions is not None and ext not in self.extensions.items:
                    continue
                path = os.path.join(root, basename)
                self.file_paths.items.append(path)

