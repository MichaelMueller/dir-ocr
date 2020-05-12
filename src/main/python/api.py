import os

import api_interface
from typing import List
import numpy as np
import threading
import time
import sqlite3

class IndexJob(api_interface.IndexJob):

    def __init__(self, path, db_factory: api_interface.DbFactory):
        self.path = path
        self.db_factory = db_factory
        self.__messages_mutex = threading.Lock()

        self.stop = False
        self.curr_file_idx = None
        self.num_files = None
        self.status = None  # type: str
        self.__messages = None  # type: List[str]
        self.finished = False
        self.__db = None # type: sqlite3.Connection

    def start(self):
        # init vars
        self.stop = False
        self.curr_file_idx = None
        self.num_files = None
        self.status = None  # type: str
        self.__messages = []  # type: List[str]
        self.finished = False
        self.__db = self.db_factory.create()
        # start thread
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):

        # get dir id
        c = self.__db.cursor()
        res = c.execute("select id from directories where path = ?", (self.path, )).fetchone()
        if len(res) > 0:
            dir_id = res[0]
        else:
            c.execute("insert into 'directories' (path) values (?)", (self.path,))
            dir_id = c.lastrowid

        self.status = "Scanning files in {}".format(self.path)
        scan_files = []
        for root, dirs, files in os.walk(self.path):
            if self.check_stop():
                return
            for basename in files:
                if self.check_stop():
                    return
                file_name, ext = os.path.splitext(basename)
                ext = ext[1:].lower()
                if len(self.extensions) > 0 and ext not in self.extensions:
                    continue
                path = os.path.join(root, basename).replace("\\", "/")
                scan_files.append(path)
        num_files = len(scan_files)
        self.status = "Scanning files finished. Found {} files for indexing.".format(num_files)

        self.num_files = 60

        for i in range(self.num_files):
            if self.stop:
                break
            self.curr_file_idx = i

            # heavy task
            self.status = "Indexing file {} of {}".format(i, self.num_files)
            with self.__messages_mutex:
                self.__messages.append("Processing file {} of {}".format(i, self.num_files))
            time.sleep(1)

        self.finished = True

    def stop(self):
        self.stop = True

    def get_curr_file_index(self) -> int:
        return self.curr_file_idx

    def get_num_files(self) -> str:
        return self.curr_file_idx

    def get_status(self) -> int:
        return self.status

    def get_messages(self) -> List[str]:
        messages = []
        with self.__messages_mutex:
            for message in self.__messages:
                messages.append(message)
            self.__messages.clear()
        return messages

    def is_finished(self) -> bool:
        return self.finished


class Result(api_interface.Result):

    def __init__(self, data_tuple, preview_image=None):
        self.path = data_tuple[0]
        self.path = data_tuple[1]
        self.path = data_tuple[2]
        self.preview_image = preview_image

    def get_path(self) -> str:
        return self.path

    def get_text(self) -> str:
        return self.text

    def get_page(self) -> int:
        return self.page

    def get_preview_image(self) -> np.ndarray:
        return self.preview_image


class WheresTheFckReceipt(api_interface.WheresTheFckReceipt):

    def __init__(self, factory: api_interface.Factory):
        self.factory = factory

    def add_directory(self, directory) -> IndexJob:
        return IndexJob()

    def remove_directory(self, directory):
        pass

    def update_directory(self, directory):
        pass

    def reindex_directory(self, directory) -> IndexJob:
        return IndexJob()

    def search(self, search_string, create_preview=False) -> List[Result]:
        return None
