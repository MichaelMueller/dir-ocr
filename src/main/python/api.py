import hashlib
import os
import random
import sqlite3
import string
import sys
import threading
import time
from typing import List

import cv2
import numpy as np
from pdf2image import convert_from_path
from pytesseract import pytesseract, Output

import api_interface


class IndexJob(api_interface.IndexJob):

    def __init__(self, path, db_factory: api_interface.DbFactory, app_data_path):
        self.path = path
        self.db_factory = db_factory
        self.app_data_path = app_data_path

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
        return self.num_files

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
                if ext not in ["jpg", "jpeg", "png", "bmp", "pdf"]:
                    continue
                path = os.path.join(root, basename).replace("\\", "/")
                scan_files.append(path)
        return scan_files

    def __process_image_file(self, c: sqlite3.Cursor, path, dir_id, doc_path, page):

        if c.execute("select id from images where path = ?", (path,)).fetchone() is not None:
            self.__add_message("Skipping already indexed file {}.".format(path.replace(self.path + "/", "")))
            return

        c.execute("insert into 'images' (path, directory_id) values (?, ?)", (path, dir_id))
        image_id = c.lastrowid
        img = cv2.imread(path)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(img_gray, (9, 9), 0)
        img = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        # img = 255 - thresh
        # cv2.imwrite(path.replace(self.path, "C:/Users/mueller/Desktop/output"), img)
        # img = remove_noise.process_image_for_ocr(path)
        d = pytesseract.image_to_data(img, output_type=Output.DICT)

        for j in range(len(d["text"])):
            if not d['text'][j].strip():
                continue
            c.execute(
                "insert into 'texts' (text, left, top, width, height, image_id) values (?, ?, ?, ?, ?, ?)",
                (d['text'][j], d['left'][j], d['top'][j], d['width'][j], d['height'][j], image_id))

        if doc_path and page:
            doc_id = c.execute("select id from documents where path = ?", (doc_path,)).fetchone()
            if doc_id is None:
                c.execute("insert into documents (path, directory_id) values (?, ?)", (doc_path, dir_id))
                doc_id = c.lastrowid
            else:
                doc_id = doc_id[0]
            c.execute("update images set document_id = ?, doc_page = ? where id = ?", (doc_id, page, image_id))

    def run(self):
        try:
            # get dir id
            db = self.db_factory.create()
            c = db.cursor()
            res = c.execute("select id from directories where path = ?", (self.path,)).fetchone()
            if res is not None:
                dir_id = res[0]
            else:
                c.execute("insert into 'directories' (path) values (?)", (self.path,))
                dir_id = c.lastrowid
                db.commit()

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
                    "File {} of {}: Analyzing {}.".format(i + 1, self.num_files, rel_path))

                _, ext = os.path.splitext(path)
                image_paths = []
                if ext.lower() == ".pdf":

                    self.__add_message(
                        "Converting {} to single image files.".format(rel_path))
                    images = convert_from_path(path, 300)
                    page = 0
                    for image in images:
                        page = page + 1
                        # while True:
                        #    img_path = self.app_data_path + "/" + self.random_string() + ".png"
                        #    if not os.path.exists(img_path):
                        #        break
                        img_path = self.app_data_path + "/" + hashlib.md5(path.encode('utf-8')).hexdigest() + "_page" + str(
                            page) + ".jpg"
                        self.__add_message(
                            "Writing page {} of {} as image {}.".format(page, len(images), img_path))
                        # cv2.imwrite(img_path, image)
                        image.save(img_path, 'JPEG')
                        image_paths.append((img_path, path, page))
                else:
                    image_paths = [(path, None, None)]

                for img_path in image_paths:
                    self.__add_message(
                        "Extracting text from {}.".format(
                                                                         img_path[0].replace(self.path + "/", "")))
                    try:
                        self.__process_image_file(c, img_path[0], dir_id, img_path[1], img_path[2])
                    except:
                        self.__add_message("An unknown error occured while converting {}".format(img_path[0].replace(self.path + "/", "")))
                db.commit()

            # commit or rollback
            if self._stop:
                self.__add_message("Indexing stopped")
                db.rollback()
            else:
                self.__add_message("Indexing successfully finished")
                db.commit()
            self.finished = True
        finally:  # catch *all* exceptions
            self._stop = True
            db.rollback()
            #e = sys.exc_info()[0]
            self.__add_message("An unknown error occured")

    def random_string(self, stringLength=5):
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(stringLength))


class Result(api_interface.Result):

    def __init__(self, path, text, page, doc_path, top, left, width, height):
        self.path = path
        self.text = text
        self.page = page
        self.doc_path = doc_path
        self.top = top
        self.left = left
        self.width = width
        self.height = height

    def get_path(self) -> str:
        return self.path

    def get_text(self) -> str:
        return self.text

    def get_page(self) -> int:
        return self.page

    def get_preview_image(self) -> np.ndarray:
        preview_image = None

        if not os.path.exists(self.path):
            return None
        image = cv2.imread(self.path)
        overlay = image.copy()

        x, y, w, h = self.left, self.top, self.width, self.height  # Rectangle parameters
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), -1)  # A filled rectangle

        alpha = 0.7  # Transparency factor.

        # Following line overlays transparent rectangle over the image
        preview_image = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)

        return preview_image


class WheresTheFckReceipt(api_interface.WheresTheFckReceipt):

    def __init__(self, app_data_dir, db_factory: api_interface.DbFactory,
                 index_job_factory: api_interface.IndexJobFactory):
        self.app_data_dir = app_data_dir
        self.db_factory = db_factory
        self.index_job_factory = index_job_factory
        self.db = None

    def get_last_directory(self) -> str:
        self.assert_db()
        c = self.db.cursor()
        c.execute("select path from directories order by id desc limit 1")
        row = c.fetchone()
        return row[0] if row and os.path.exists(row[0]) else None

    def assert_db(self):
        if not self.db:
            self.db = self.db_factory.create()

    def get_directories(self) -> List[str]:
        self.assert_db()
        c = self.db.cursor()
        c.execute("select path from directories")
        rows = c.fetchall()
        return [i[0] for i in rows]

    def add_directory(self, directory) -> IndexJob:
        return self.index_job_factory.create(directory, self.db_factory, self.app_data_dir)

    def remove_directory(self, directory):
        self.assert_db()
        c = self.db.cursor()
        own_images = c.execute(
            "select path from images, directories where directories.id = images.directory_id and images.document_id != null")
        for own_image in own_images.fetchall():
            os.remove(own_image[0])
        c.execute("delete from directories where path = ?", (directory,))
        self.db.commit()

    def update_directory(self, directory):
        return self.index_job_factory.create(directory, self.db_factory, self.app_data_dir)

    def reindex_directory(self, directory) -> IndexJob:
        self.remove_directory(directory)
        return self.add_directory(directory)

    def search(self, query, limit=None) -> List[Result]:
        c = self.db.cursor()
        query = "%" + query + "%"
        sql = "select images.path as path, texts.text as text, images.doc_page as page, images.document_id as doc_id, texts.top as top, texts.left as left, texts.width as width, texts.height as height from images, texts where texts.image_id = images.id and texts.text like ?"
        if limit:
            sql = sql + " limit ?"
            c.execute(sql, (query, limit))
        else:
            c.execute(sql, (query,))
        result_list = []
        rows = c.fetchall()
        for row in rows:
            doc_id = row[3]
            doc_path = c.execute("select path from documents where id = ?", (doc_id,)).fetchone()[0] if doc_id else None

            # path, text, page, doc_path, top, left, width, height
            result_list.append(Result(row[0], row[1], row[2], doc_path, row[4], row[5], row[6], row[7]))
        # return [i[0] for i in rows]
        return result_list


class IndexJobFactory(api_interface.IndexJobFactory):

    def create(self, path, db_factory: api_interface.DbFactory, app_data_dir) -> IndexJob:
        return IndexJob(path, db_factory, app_data_dir)


class DbFactory(api_interface.DbFactory):
    def __init__(self, app_data_dir: str, delete_db=False):
        self.app_data_dir = app_data_dir
        self.db_path = app_data_dir + "/db.sqlite3";
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
                "CREATE TABLE images ( id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE NOT NULL, directory_id INTEGER NOT NULL, document_id INTEGER, doc_page INTEGER, FOREIGN KEY(directory_id) REFERENCES directories(id) ON DELETE CASCADE, FOREIGN KEY(document_id) REFERENCES documents(id) )")
            c.execute(
                "CREATE TABLE texts ( id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, left INTEGER  NOT NULL, top INTEGER NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, image_id INTEGER NOT NULL, FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE )")
            db.commit()
        return db
