import abc
import os
from typing import List, Optional
import tempfile
from pdf2image import convert_from_path


class FileProcessor:
    @abc.abstractmethod
    def process(self, full_path, basename, file_name, ext):
        pass


class FilePathsFromDirectory:
    def __init__(self):
        self.directory = None  # type: Optional[str]
        self.extensions = None  # type: List[Optional[str]]
        self.file_processor = None  # type: FileProcessor

    def run(self):
        for root, dirs, files in os.walk(self.directory.val):
            for basename in files:
                file_name, ext = os.path.splitext(basename)
                ext = ext[1:].lower()
                if self.extensions is not None and ext not in self.extensions.items:
                    continue
                path = os.path.join(root, basename)

                self.file_processor.process(path, basename, file_name, ext)

class TesseractProcessor(FileProcessor):

    def process(self, full_path, basename, file_name, ext):
        if ext == "pdf":
            with tempfile.TemporaryDirectory() as path:
                images_from_path = convert_from_path(full_path, output_folder=path)

class DirOcr:

    def run(self):
        pass