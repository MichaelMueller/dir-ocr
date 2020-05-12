import api_interface
from typing import List
import numpy as np
import threading
import time


class IndexJob(api_interface.IndexJob):

    def __init__(self):
        self.stop = False
        self.curr_file_idx = None
        self.num_files = None
        self.status = None  # type: str
        self.__messages_mutex = threading.Lock()
        self.__messages = []  # type: List[str]
        self.finished = False

    def start(self):
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):

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