# WheresTheFckReceipt
#   Indexer
#       DirWalker
#       FileToImageConverter
#
import os
import sqlite3
import sys
import abc
import cv2

from PyQt5.QtCore import QDateTime, QStandardPaths, QFile, QFileInfo, Qt
from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout, \
    QTabWidget, QTextEdit, QApplication, QProgressBar, QFileDialog, QMessageBox, QLineEdit

########### Abstract Classes
from pytesseract import pytesseract, Output

class IndexerObserver:
    @abc.abstractmethod
    def status_changed(self, status, type=0):
        pass

    @abc.abstractmethod
    def location_added(self, location):
        pass

    @abc.abstractmethod
    def location_removed(self, location):
        pass

    @abc.abstractmethod
    def current_file_index_changed(self, file_index, num_files):
        pass

    @abc.abstractmethod
    def indexing_finished(self, num_files):
        pass

########### Backend
class Searcher:
    def __init__(self, db):
        self.db = db  # type: sqlite3.Connection

    def search(self, query):
        c = self.db.cursor()
        c.execute("select images.path as path from images, texts where texts.image_id = images.id and texts.text like ?", (query,))
        rows = c.fetchall()
        return [i[0] for i in rows]

class Indexer:
    def __init__(self):
        self.observer = None  # type: IndexerObserver
        self.db = None  # type: sqlite3.Connection
        self.extensions = ["jpg", "jpeg", "png", "bmp"]
        self.stop_ = False

    def set_observer(self, observer):
        self.observer = observer

    def get_locations(self):
        c = self.get_db_cursor()
        c.execute("select path from locations")
        rows = c.fetchall()
        return [i[0] for i in rows]

    def stop(self):
        self.stop_ = True

    def check_stop(self):
        if self.stop_:
            self.stop_ = False
            self.db.rollback()
            self.observer.indexing_finished()
            return True
        else:
            return False

    def add_location(self, location_path):

        c = self.get_db_cursor()
        try:
            c.execute("insert into 'locations' (path) values (?)", (location_path,))
        except sqlite3.Error:
            self.observer.status_changed("Aborting... the location " + location_path + " already exists.", 1)
            return
        location_id = c.lastrowid

        self.observer.status_changed("Scanning files")
        scan_files = []
        for root, dirs, files in os.walk(location_path):
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
        self.observer.status_changed("Scanning files finished. Found {} files for indexing.".format(num_files))

        for i in range(num_files):
            if self.check_stop():
                return
            self.observer.current_file_index_changed(i, num_files)
            path = scan_files[i]
            rel_path = path.replace(location_path + "/", "")
            try:
                c.execute("insert into 'images' (path, location_id) values (?, ?)", (path, location_id,))
                image_id = c.lastrowid
                self.observer.status_changed("Extracting text from {}.".format(rel_path))
                img = cv2.imread(path)
                d = pytesseract.image_to_data(img, output_type=Output.DICT)

                try:
                    for j in range(len(d["text"])):
                        if not d['text'][j].strip():
                            continue
                        c.execute(
                            "insert into 'texts' (text, left, top, width, height, image_id) values (?, ?, ?, ?, ?, ?)",
                            (d['text'][j], d['left'][j], d['top'][j], d['width'][j], d['height'][j], image_id))
                except sqlite3.Error as e:
                    self.observer.status_changed("Unknown error while storing texts in database {}.".format(str(e)), 2)
            except sqlite3.Error:
                self.observer.status_changed("Skipping already indexed file {}.".format(rel_path), 2)

        self.db.commit()
        self.observer.location_added(location_path)
        self.observer.indexing_finished()

    def remove_location(self, location_path):
        c = self.get_db_cursor()
        try:
            c.execute("delete from 'locations' where path = ?", (location_path,))
            self.db.commit()
            self.observer.location_removed(location_path)
        except sqlite3.Error:
            self.observer.status_changed("Aborting... the location " + location_path + " cannot be deleted.", 1)
            return

    def __del__(self):
        self.close_db()

    def close_db(self):
        if self.db is not None:
            self.db.close()
            self.db = None

    def get_db(self):
        self.get_db_cursor()
        return self.db

    def get_db_cursor(self):
        # database
        db_path = QFileInfo(
            QStandardPaths.writableLocation(QStandardPaths.DataLocation) + "/" + ApplicationContext().build_settings[
                'app_name'] + ".sqlite3")
        if not os.path.exists(db_path.absolutePath()):
            os.makedirs(db_path.absolutePath())
        init_database = not os.path.exists(db_path.absoluteFilePath())
        self.db = sqlite3.connect(db_path)
        c = self.db.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        if init_database:
            c.execute("CREATE TABLE 'locations' ( 'id' INTEGER PRIMARY KEY AUTOINCREMENT, 'path' TEXT UNIQUE )")
            c.execute(
                "CREATE TABLE 'images' ( 'id' INTEGER PRIMARY KEY AUTOINCREMENT, 'path' TEXT UNIQUE, 'location_id' INTEGER NOT NULL, FOREIGN KEY('location_id') REFERENCES 'locations'('id') ON DELETE CASCADE )")
            c.execute(
                "CREATE TABLE 'texts' ( 'id' INTEGER PRIMARY KEY AUTOINCREMENT, 'text' TEXT, 'left' INTEGER, 'top' INTEGER, 'width' INTEGER, 'height' INTEGER, 'image_id' INTEGER NOT NULL, FOREIGN KEY('image_id') REFERENCES 'images'('id') ON DELETE CASCADE )")
            self.db.commit()
        return c


# Indexer

# Widgets
class ConsoleWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setAcceptRichText(True)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0);
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def set_text(self, text):
        datetime = QDateTime.currentDateTime()
        self.text_edit.append(datetime.toString() + ", " + text)
        QApplication.processEvents()

    def info(self, text):
        self.set_text("INFO: " + text)

    def warn(self, text):
        self.set_text("<font color='orange'>WARN</font>: " + text)

    def error(self, text):
        self.set_text("<font color='red'>ERR</font>: " + text)

class SearcherWidget(QWidget):
    def __init__(self, parent, searcher):
        QWidget.__init__(self, parent)
        self.searcher = searcher # type: Searcher

        # query
        self.query = QLineEdit()
        search_button = QPushButton('Search')
        search_button.clicked.connect(self.search_button_clicked)
        query_bar_layout = QHBoxLayout()
        query_bar_layout.addWidget(self.query)
        query_bar_layout.addWidget(search_button)

        # the file_list
        self.match_list = QListWidget()

        # my layout
        layout = QVBoxLayout()
        layout.addLayout(query_bar_layout)
        layout.addWidget(self.match_list)
        self.setLayout(layout)

    def search_button_clicked(self):
        matches = self.searcher.search(self.query.text())
        self.match_list.clear()
        for match in matches:
            self.match_list.addItem(match)

class IndexerWidget(QWidget, IndexerObserver):
    def __init__(self, parent, indexer):
        QWidget.__init__(self, parent)

        # vars
        self.indexer = indexer  # type: Indexer
        self.indexer.set_observer(self)

        ## GUI
        # locations
        self.locations = QListWidget()
        self.locations.itemSelectionChanged.connect(self.locations_selection_changed)
        for location in self.indexer.get_locations():
            self.locations.addItem(location)

        # the locations_action_bar
        self.add_location_button = QPushButton('Add Location')
        self.add_location_button.clicked.connect(self.add_location_button_clicked)
        self.add_location_button.setEnabled(True)
        self.remove_button = QPushButton('Remove')
        self.remove_button.clicked.connect(self.remove_button_clicked)
        self.remove_button.setEnabled(False)
        self.reindex_button = QPushButton('Re-Index')
        self.reindex_button.clicked.connect(self.reindex_button_clicked)
        self.reindex_button.setEnabled(False)
        file_list_action_bar_layout = QHBoxLayout()
        file_list_action_bar_layout.setContentsMargins(0, 0, 0, 0);
        file_list_action_bar_layout.addWidget(self.add_location_button)
        file_list_action_bar_layout.addWidget(self.remove_button)
        file_list_action_bar_layout.addWidget(self.reindex_button)
        file_list_action_bar_widget = QWidget()
        file_list_action_bar_widget.setLayout(file_list_action_bar_layout)

        # index_status_widget
        self.index_status_label = QLabel("")
        self.index_progress_bar = QProgressBar()
        self.stop_index_button = QPushButton('Stop Indexing')
        self.stop_index_button.clicked.connect(self.stop_index_button_clicked)
        self.stop_index_button.setEnabled(False)
        index_status_widget_layout = QHBoxLayout()
        index_status_widget_layout.setContentsMargins(0, 0, 0, 0)
        index_status_widget_layout.addWidget(self.index_status_label)
        index_status_widget_layout.addWidget(self.index_progress_bar)
        index_status_widget_layout.addWidget(self.stop_index_button)
        index_status_widget = QWidget()
        index_status_widget.setLayout(index_status_widget_layout)

        # index console
        self.index_console = ConsoleWidget()

        # layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Locations:"))
        layout.addWidget(self.locations)
        layout.addWidget(file_list_action_bar_widget)
        layout.addWidget(index_status_widget)
        layout.addWidget(self.index_console)
        self.setLayout(layout)

    def stop_index_button_clicked(self):
        self.indexer.stop()

    def locations_selection_changed(self):
        list_items = self.locations.selectedItems()
        if not list_items:
            self.remove_button.setEnabled(False)
            self.reindex_button.setEnabled(False)
        else:
            self.remove_button.setEnabled(True)
            self.reindex_button.setEnabled(True)

    def add_location_button_clicked(self):
        directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        if directory:
            self.add_location_button.setEnabled(False)
            self.locations.setEnabled(False)
            self.stop_index_button.setEnabled(True)
            self.remove_button.setEnabled(False)
            self.reindex_button.setEnabled(False)
            self.indexer.add_location(directory)

    def remove_button_clicked(self):
        answer = QMessageBox.question(self, "Remove location", "Proceed?")
        if answer == QMessageBox.Yes:
            selected_location = self.locations.currentItem().text()
            self.indexer.remove_location(selected_location)

    def reindex_button_clicked(self):
        answer = QMessageBox.question(self, "Re-Index location", "Proceed?")
        if answer == QMessageBox.Yes:
            selected_location = self.locations.currentItem().text()
            self.indexer.remove_location(selected_location)
            self.indexer.add_location(selected_location)

    def status_changed(self, status, type=0):
        if type == 1:
            self.index_console.error(status)
        elif type == 2:
            self.index_console.warn(status)
        else:
            self.index_console.info(status)

    def location_added(self, location):
        self.locations.addItem(location)

    def location_removed(self, location):
        items = self.locations.findItems(location, Qt.MatchExactly)
        if len(items) > 0:
            for item in items:
                self.locations.takeItem(self.locations.row(item))

    def current_file_index_changed(self, file_index, num_files):
        if file_index == 0:
            self.index_progress_bar.setRange(0, num_files)
        self.index_status_label.setText("Indexing file {} of {}".format(file_index + 1, num_files))
        self.index_progress_bar.setValue(file_index)

        QApplication.processEvents()

    def indexing_finished(self):
        self.index_progress_bar.setValue(self.index_progress_bar.maximum())
        self.stop_index_button.setEnabled(False)
        self.add_location_button.setEnabled(True)
        self.locations.setEnabled(True)
        self.remove_button.setEnabled(self.locations.currentRow() >= 0)
        self.reindex_button.setEnabled(self.locations.currentRow() >= 0)

class WheresTheFckReceipt:

    def __init__(self):
        pass

    def run(self):
        # get app context
        app_context = ApplicationContext()

        # window title
        version = app_context.build_settings['version']
        app_name = app_context.build_settings['app_name']
        window_title = app_name + " v" + version
        window = QMainWindow()
        window.setWindowTitle(window_title)

        # central tab widget
        tab_widget = QTabWidget()

        # indexer
        indexer = Indexer()
        indexer_widget = IndexerWidget(None, indexer)
        tab_widget.addTab(indexer_widget, "Indexer")

        # searcher
        searcher = Searcher(indexer.get_db())
        searcher_widget = SearcherWidget(None, searcher)
        tab_widget.addTab(searcher_widget, "Searcher")

        window.setCentralWidget(tab_widget)
        window.resize(800, 600)
        window.show()
        # window.showMaximized()

        exit_code = app_context.app.exec_()  # 2. Invoke app_context.app.exec_()
        indexer.close_db()
        sys.exit(exit_code)