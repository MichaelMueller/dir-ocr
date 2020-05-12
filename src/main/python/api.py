import os
import sqlite3
import threading
import time
from typing import List

import cv2
import numpy as np
from pytesseract import pytesseract, Output

import api_interface


class IndexJob(api_interface.IndexJob):

    def __init__(self, path, db_factory: api_interface.DbFactory):
        self.path = path
        self.db_factory = db_factory

        self._stop = False
        self.curr_file_idx = None
        self.num_files = None
        self.status = None  # type: str
        self.finished = False

        self.__messages_mutex = threading.Lock()
        self.__messages = None  # type: List[str]

    def start(self):
        # init vars
        self._stop = False
        self.curr_file_idx = None
        self.num_files = None
        self.__messages = []  # type: List[str]
        self.finished = False
        # start thread
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def stop(self):
        self._stop = True

    def get_path(self) -> str:
        return self.path

    def get_curr_file_index(self) -> int:
        return self.curr_file_idx

    def get_num_files(self) -> str:
        return self.curr_file_idx

    def get_messages(self) -> List[str]:
        messages = []
        with self.__messages_mutex:
            for message in self.__messages:
                messages.append(message)
            self.__messages.clear()
        return messages

    def is_finished(self) -> bool:
        return self.finished

    def __add_message(self, msg):
        with self.__messages_mutex:
            self.__messages.append(msg)

    def __get_files(self):
        scan_files = []
        for root, dirs, files in os.walk(self.path):
            for basename in files:
                if self._stop:
                    return []
                file_name, ext = os.path.splitext(basename)
                ext = ext[1:].lower()
                if ext not in ["jpg", "jpeg", "png", "bmp"]:
                    continue
                path = os.path.join(root, basename).replace("\\", "/")
                scan_files.append(path)
        return scan_files

    def __process_image_file(self, c: sqlite3.Cursor, path, dir_id):

        if c.execute("select id from images where path = ?", (path,)).fetchone() is not None:
            self.__add_message("Skipping already indexed file {}.".format(path.replace(self.path + "/", "")), 2)
            return

        c.execute("insert into 'images' (path, directory_id) values (?, ?)", (path, dir_id,))
        image_id = c.lastrowid
        img = cv2.imread(path)
        d = pytesseract.image_to_data(img, output_type=Output.DICT)

        for j in range(len(d["text"])):
            if not d['text'][j].strip():
                continue
            c.execute(
                "insert into 'texts' (text, left, top, width, height, image_id) values (?, ?, ?, ?, ?, ?)",
                (d['text'][j], d['left'][j], d['top'][j], d['width'][j], d['height'][j], image_id))

    def run(self):

        # get dir id
        db = self.db_factory.create()
        c = db.cursor()
        res = c.execute("select id from directories where path = ?", (self.path,)).fetchone()
        if res is not None:
            dir_id = res[0]
        else:
            c.execute("insert into 'directories' (path) values (?)", (self.path,))
            dir_id = c.lastrowid

        # collect files
        self.__add_message("Scanning files in {}".format(self.path))
        scan_files = self.__get_files()
        self.num_files = len(scan_files)
        self.__add_message("Scanning files finished. Found {} files for indexing.".format(self.num_files))

        # process files
        for i in range(self.num_files):
            if self._stop:
                break
            self.curr_file_idx = i
            path = scan_files[i]
            rel_path = path.replace(self.path + "/", "")
            self.__add_message(
                "File {} of {}: Extracting text from {}.".format(i + 1, self.num_files, rel_path))
            self.__process_image_file(c, path, dir_id)

        # commit or rollback
        if self._stop:
            self.__add_message("Indexing stopped")
            db.rollback()
        else:
            self.__add_message("Indexing successfully finished")
            db.commit()
        self.finished = True


class Result(api_interface.Result):

    def __init__(self, data_tuple):
        self.path = data_tuple[0]
        self.path = data_tuple[1]
        self.path = data_tuple[2]

    def get_path(self) -> str:
        return self.path

    def get_text(self) -> str:
        return self.text

    def get_page(self) -> int:
        return self.page

    def get_preview_image(self) -> np.ndarray:
        preview_image = None
        return preview_image


class WheresTheFckReceipt(api_interface.WheresTheFckReceipt):

    def __init__(self, db_factory: api_interface.DbFactory, index_job_factory: api_interface.IndexJobFactory):
        self.db_factory = db_factory
        self.index_job_factory = index_job_factory
        self.db = None

    def assert_db(self):
        if not self.db:
            self.db = self.db_factory.create()

    def get_directories(self) -> List[str]:
        self.assert_db()
        c = self.db.cursor()
        c.execute("select path from locations")
        rows = c.fetchall()
        return [i[0] for i in rows]

    def add_directory(self, directory) -> IndexJob:
        return self.index_job_factory.create(directory, self.db_factory)

    def remove_directory(self, directory):
        self.assert_db()
        c = self.db.cursor()
        c.execute("delete from locations where path = ?", (path,))

    def update_directory(self, directory):
        return self.index_job_factory.create(directory, self.db_factory)

    def reindex_directory(self, directory) -> IndexJob:
        self.remove_directory(directory)
        return self.add_directory(directory)

    def search(self, query, limit=None) -> List[Result]:
        c = self.db.cursor()
        sql = "select images.path as path, texts.text as text from images, texts where texts.image_id = images.id and texts.text like ?"
        if limit:
            sql = sql + " limit ?"
            c.execute(sql, (query, limit))
        else:
            c.execute(sql, (query,))
        result_list = []
        rows = c.fetchall()
        for row in rows:
            result_list.append(Result(row))
        # return [i[0] for i in rows]
        return result_list


class IndexJobFactory(api_interface.IndexJobFactory):

    def create(self, path, db_factory: api_interface.DbFactory) -> IndexJob:
        return IndexJob(path, db_factory)


class DbFactory(api_interface.DbFactory):
    def __init__(self, app_dir_path: api_interface.AppDataDirPath, delete_db=False):
        self.db_path = app_dir_path.get() + "/db.sqlite3";
        if delete_db and os.path.exists(self.db_path):
            os.remove(self.db_path)

    def create(self) -> sqlite3.Connection:
        # database
        db_path = self.db_path
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path))
        init_database = not os.path.exists(db_path)

        db = sqlite3.connect(db_path)
        c = db.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        if init_database:
            c.execute("CREATE TABLE directories ( id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE )")
            c.execute(
                "CREATE TABLE documents ( id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE NOT NULL, directory_id INTEGER NOT NULL, FOREIGN KEY(directory_id) REFERENCES directories(id) ON DELETE CASCADE )")
            c.execute(
                "CREATE TABLE images ( id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE NOT NULL, directory_id INTEGER NOT NULL, document_id INTEGER, dcoument_page INTEGER, FOREIGN KEY(directory_id) REFERENCES directories(id) ON DELETE CASCADE, FOREIGN KEY(document_id) REFERENCES documents(id) )")
            c.execute(
                "CREATE TABLE texts ( id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, left INTEGER  NOT NULL, top INTEGER NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, image_id INTEGER NOT NULL, FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE )")
            db.commit()
        return db
