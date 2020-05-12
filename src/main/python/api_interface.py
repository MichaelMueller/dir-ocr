import abc
from typing import List
import numpy as np


# ABSTRACT DESIGN
class IndexJob:
    @abc.abstractmethod
    def start(self):
        return None

    @abc.abstractmethod
    def stop(self):
        return None

    @abc.abstractmethod
    def get_curr_file_index(self) -> int:
        return None

    @abc.abstractmethod
    def get_num_files(self) -> int:
        return None

    @abc.abstractmethod
    def get_messages(self) -> List[str]:
        return None

    @abc.abstractmethod
    def get_status(self) -> str:
        return None

    @abc.abstractmethod
    def is_finished(self) -> bool:
        return False


class Result:
    @abc.abstractmethod
    def get_path(self) -> str:
        return None

    @abc.abstractmethod
    def get_text(self) -> str:
        return None

    @abc.abstractmethod
    def get_page(self) -> int:
        return None

    @abc.abstractmethod
    def get_preview_image(self) -> np.ndarray:
        return None


class WheresTheFckReceipt:
    def add_directory(self, directory) -> IndexJob:
        return None

    def remove_directory(self, directory):
        pass

    def update_directory(self, directory):
        pass

    def reindex_directory(self, directory) -> IndexJob:
        return None

    def search(self, search_string, create_preview=False) -> List[Result]:
        return None
