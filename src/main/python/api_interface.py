import abc
from typing import List
import numpy as np
import sqlite3


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
    @abc.abstractmethod
    def add_directory(self, directory) -> IndexJob:
        return None

    @abc.abstractmethod
    def remove_directory(self, directory):
        pass

    @abc.abstractmethod
    def update_directory(self, directory):
        pass

    @abc.abstractmethod
    def reindex_directory(self, directory) -> IndexJob:
        return None

    @abc.abstractmethod
    def search(self, search_string) -> List[Result]:
        return None


class DbFactory:

    @abc.abstractmethod
    def create(self) -> sqlite3.Connection:
        return None


class IndexJobFactory:

    @abc.abstractmethod
    def create(self, db_connection: sqlite3.Connection) -> IndexJob:
        return None
