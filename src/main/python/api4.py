# WheresTheFckReceipt
#   Indexer
#       DirWalker
#       FileToImageConverter
#
import os
import sqlite3
import sys
import abc
import time

import cv2
from PyQt5 import QtGui, QtWidgets

from PyQt5.QtCore import QDateTime, QStandardPaths, QFile, QFileInfo, Qt, QObject, QThread, pyqtSignal
from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout, \
    QTabWidget, QTextEdit, QApplication, QProgressBar, QFileDialog, QMessageBox, QLineEdit, QTableWidget, QSpinBox, \
    QHeaderView, QTableWidgetItem, QAbstractItemView

from pytesseract import pytesseract, Output


###### MODEL
class DbFactory:
    def __init__(self, db_path, recreate_db=False):
        self.db_path = db_path  # type QFileInfo
        if recreate_db and os.path.exists(db_path.absoluteFilePath()):
            os.remove(db_path.absoluteFilePath())

    def create(self):
        # database
        db_path = self.db_path
        if not os.path.exists(db_path.absolutePath()):
            os.makedirs(db_path.absolutePath())
        init_database = not os.path.exists(db_path.absoluteFilePath())

        db = sqlite3.connect(db_path)
        c = db.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        if init_database:
            c.execute("CREATE TABLE 'directories' ( 'id' INTEGER PRIMARY KEY AUTOINCREMENT, 'path' TEXT UNIQUE )")
            c.execute(
                "CREATE TABLE 'documents' ( 'id' INTEGER PRIMARY KEY AUTOINCREMENT, 'path' TEXT UNIQUE NOT NULL, 'directory_id' INTEGER NOT NULL, FOREIGN KEY('directory_id') REFERENCES 'directories'('id') ON DELETE CASCADE )")
            c.execute(
                "CREATE TABLE 'images' ( 'id' INTEGER PRIMARY KEY AUTOINCREMENT, 'path' TEXT UNIQUE NOT NULL, 'directory_id' INTEGER NOT NULL, 'document_id' INTEGER, dcoument_page INTEGER, FOREIGN KEY('directory_id') REFERENCES 'directories'('id') ON DELETE CASCADE, FOREIGN KEY('document_id') REFERENCES 'documents'('id') )")
            c.execute(
                "CREATE TABLE 'texts' ( 'id' INTEGER PRIMARY KEY AUTOINCREMENT, 'text' TEXT NOT NULL, 'left' INTEGER  NOT NULL, 'top' INTEGER NOT NULL, 'width' INTEGER NOT NULL, 'height' INTEGER NOT NULL, 'image_id' INTEGER NOT NULL, FOREIGN KEY('image_id') REFERENCES 'images'('id') ON DELETE CASCADE )")
            db.commit()
        return db

class IndexJob(QObject):
    finished = pyqtSignal()
    directory_added = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    processed_file_index_changed = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.stop = False

    def run(self):
        i = 0
        num_files = 60
        while i < num_files and not self.stop:
            self.processed_file_index_changed.emit(i, num_files)
            time.sleep(1)
            i = i + 1

        self.finished.emit()

###### VIEWS
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

class IndexView(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent=None)

        ## GUI

        # add dir button
        self.add_directory = QPushButton('Add Directory')
        self.add_directory.setEnabled(True)

        # locations
        self.directories = QListWidget()

        # the locations_action_bar
        self.index = QPushButton('Update')
        self.index.setEnabled(False)
        self.remove_dir = QPushButton('Remove')
        self.remove_dir.setEnabled(False)
        self.re_index = QPushButton('Re-Index')
        self.re_index.setEnabled(False)
        file_list_action_bar_layout = QHBoxLayout()
        file_list_action_bar_layout.setContentsMargins(0, 0, 0, 0)
        file_list_action_bar_layout.addWidget(self.index)
        file_list_action_bar_layout.addWidget(self.remove_dir)
        file_list_action_bar_layout.addWidget(self.re_index)
        file_list_action_bar_widget = QWidget()
        file_list_action_bar_widget.setLayout(file_list_action_bar_layout)

        # index_status_widget
        self.index_status = QLabel("")
        self.index_progress = QProgressBar()
        self.stop_index = QPushButton('Stop Indexing')
        self.stop_index.setEnabled(True)
        index_status_widget_layout = QHBoxLayout()
        index_status_widget_layout.setContentsMargins(0, 0, 0, 0)
        index_status_widget_layout.addWidget(self.index_status)
        index_status_widget_layout.addWidget(self.index_progress)
        index_status_widget_layout.addWidget(self.stop_index)
        index_status_widget = QWidget()
        index_status_widget.setLayout(index_status_widget_layout)

        # index console
        self.index_console = ConsoleWidget()

        # layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Indexed Directories:"))
        layout.addWidget(self.add_directory)
        layout.addWidget(self.directories)
        layout.addWidget(file_list_action_bar_widget)
        layout.addWidget(index_status_widget)
        layout.addWidget(self.index_console)
        self.setLayout(layout)

    def current_file_index_changed(self, file_index, num_files):
        if file_index == 0:
            self.index_progress.setRange(0, num_files)
        self.index_status.setText("Indexing file {} of {}".format(file_index + 1, num_files))
        self.index_progress.setValue(file_index)

class WheresTheFckReceipt(QMainWindow):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=None)

        # build window title
        app_context = ApplicationContext()
        version = app_context.build_settings['version']
        app_name = app_context.build_settings['app_name']
        window_title = app_name + " v" + version

        # tab widget
        self.tab_widget = QTabWidget()

        # build main window
        self.setWindowTitle(window_title)
        self.setCentralWidget(self.tab_widget)
        self.resize(800, 600)

###### CONTROLLER
class IndexController(QObject):
    def __init__(self, parent, db_factory):
        super().__init__(parent=parent)

        # model
        self.db_factory = db_factory # type: DbFactory
        self.thread = None
        self.index_job = None

        # view
        self.view = IndexView()

        # connect
        self.view.add_directory.clicked.connect(self.add_directory_clicked)
        self.view.stop_index.clicked.connect(self.stop_index_clicked)

        # init model

    def stop_index_clicked(self):
        if self.thread:
            self.index_job.stop = True

    def add_directory_clicked(self):
        directory = str(QFileDialog.getExistingDirectory(self.view, "Select Directory"))
        if directory:
            self.thread = QThread()
            self.index_job = IndexJob()
            self.index_job.moveToThread(self.thread)
            self.index_job.processed_file_index_changed.connect(self.view.current_file_index_changed)
            self.index_job.finished.connect(self.thread.quit)
            self.index_job.finished.connect(self.index_job.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.started.connect(self.index_job.run)
            self.thread.start()


class AppController(QObject):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # model
        # create db
        db_path = QFileInfo(
            QStandardPaths.writableLocation(QStandardPaths.DataLocation) + "/" + ApplicationContext().build_settings[
                'app_name'] + ".sqlite3")
        recreate_db = "--recreate_db" in sys.argv
        db_factory = DbFactory(db_path, recreate_db)

        # subcontroller
        index_controller = IndexController(self, db_factory)

        # view
        self.view = AppView()
        self.view.tab_widget.addTab(index_controller.view, "Index")

        # connect

        # init model

    def start(self):
        # run the application
        app_context = ApplicationContext()
        self.view.show()
        exit_code = app_context.app.exec_()  # 2. Invoke app_context.app.exec_()
        return exit_code
