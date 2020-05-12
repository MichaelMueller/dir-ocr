import os
import sqlite3
import sys
import abc
import time

import cv2
from PyQt5 import QtGui, QtWidgets

from PyQt5.QtCore import QDateTime, QStandardPaths, QFile, QFileInfo, Qt, QObject, QThread, pyqtSignal, QTimer, \
    QSettings, QCoreApplication
from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout, \
    QTabWidget, QTextEdit, QApplication, QProgressBar, QFileDialog, QMessageBox, QLineEdit, QTableWidget, QSpinBox, \
    QHeaderView, QTableWidgetItem, QAbstractItemView

from pytesseract import pytesseract, Output
import api_interface


class Indexer(QWidget):
    def __init__(self, wheres_the_fck_receipt: api_interface.WheresTheFckReceipt, parent=None):
        QWidget.__init__(self, parent=None)
        self.wheres_the_fck_receipt = wheres_the_fck_receipt
        self.index_job = None  # type: api_interface.IndexJob
        self.index_job_timer = QTimer()
        self.index_job_timer.timeout.connect(self.index_job_timer_timeout)

        # WIDGETS
        # add dir button
        self.add_directory = QPushButton('Add Directory')
        self.add_directory.setEnabled(True)
        self.add_directory.clicked.connect(self.add_directory_clicked)

        # locations
        self.directories = QListWidget()
        self.directories.itemSelectionChanged.connect(self.directories_selection_changed)
        self.directories.setSelectionMode(QAbstractItemView.SingleSelection)
        for dir in self.wheres_the_fck_receipt.get_directories():
            self.directories.addItem(dir)

        # the locations_action_bar
        self.index = QPushButton('Update')
        self.index.clicked.connect(self.update_clicked)
        self.remove_dir = QPushButton('Remove')
        self.remove_dir.clicked.connect(self.remove_clicked)
        self.re_index = QPushButton('Re-Index')
        self.re_index.clicked.connect(self.reindex_clicked)
        file_list_action_bar_layout = QHBoxLayout()
        file_list_action_bar_layout.setContentsMargins(0, 0, 0, 0)
        file_list_action_bar_layout.addWidget(self.index)
        file_list_action_bar_layout.addWidget(self.remove_dir)
        file_list_action_bar_layout.addWidget(self.re_index)
        self.file_list_action_bar_widget = QWidget()
        self.file_list_action_bar_widget.setLayout(file_list_action_bar_layout)
        self.file_list_action_bar_widget.setEnabled(False)

        # index_status_widget
        self.index_progress = QProgressBar()
        self.index_progress.setEnabled(False)
        self.stop_index = QPushButton('Stop Indexing')
        self.stop_index.setEnabled(False)
        self.stop_index.clicked.connect(self.stop_index_clicked)
        index_status_widget_layout = QHBoxLayout()
        index_status_widget_layout.setContentsMargins(0, 0, 0, 0)
        index_status_widget_layout.addWidget(self.index_progress)
        index_status_widget_layout.addWidget(self.stop_index)
        index_status_widget = QWidget()
        index_status_widget.setLayout(index_status_widget_layout)

        # index console
        self.index_console = QTextEdit()
        self.index_console.setReadOnly(True)
        self.index_console.setEnabled(False)

        # layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Indexed Directories:"))
        layout.addWidget(self.add_directory)
        layout.addWidget(self.directories)
        layout.addWidget(self.file_list_action_bar_widget)
        layout.addWidget(QLabel("Indexer Status:"))
        layout.addWidget(index_status_widget)
        layout.addWidget(self.index_console)
        self.setLayout(layout)

    def directories_selection_changed(self):
        list_items = self.directories.selectedItems()
        self.file_list_action_bar_widget.setEnabled(len(list_items) == 1)

    def add_directory_clicked(self):
        directory = str(QFileDialog.getExistingDirectory(self, "Select Directory",
                                                         self.wheres_the_fck_receipt.get_last_directory(),
                                                         QFileDialog.ShowDirsOnly))
        if directory:
            # get the job
            self.index_job = self.wheres_the_fck_receipt.add_directory(directory)
            self.run_indexer()

    def run_indexer(self):
        # manage gui
        self.add_directory.setEnabled(False)
        self.directories.setEnabled(False)
        self.file_list_action_bar_widget.setEnabled(False)
        self.index_progress.setEnabled(True)
        self.index_progress.reset()
        self.stop_index.setEnabled(True)
        self.index_console.setEnabled(True)
        self.index_console.clear()
        # start job
        self.stop_index.setEnabled(True)
        self.index_job.start()
        self.index_job_timer.start(500)

    def update_clicked(self):
        self.index_job = self.wheres_the_fck_receipt.update_directory(self.directories.currentItem().text())
        self.run_indexer()

    def remove_clicked(self):
        self.wheres_the_fck_receipt.remove_directory(self.directories.currentItem().text())
        self.directories.takeItem(self.directories.currentRow())

    def reindex_clicked(self):
        self.index_job = self.wheres_the_fck_receipt.reindex_directory(self.directories.currentItem().text())
        self.run_indexer()

    def stop_index_clicked(self):
        self.index_job.stop()
        self.indexing_stopped()

    def indexing_stopped(self):
        self.index_job_timer.stop()
        self.add_directory.setEnabled(True)
        self.directories.setEnabled(True)
        self.file_list_action_bar_widget.setEnabled(len(self.directories.selectedItems()) > 0)
        self.index_progress.setEnabled(False)
        self.stop_index.setEnabled(False)
        self.index_console.setEnabled(False)
        self.index_job = None

    def index_job_timer_timeout(self):
        for msg in self.index_job.get_messages():
            self.index_console.append(msg)
        num_files = self.index_job.get_num_files()
        if num_files and self.index_progress.maximum() != num_files:
            self.index_progress.setRange(0, num_files)
        curr_file_idx = self.index_job.get_curr_file_index()
        if curr_file_idx:
            self.index_progress.setValue(curr_file_idx)
        if self.index_job.is_finished():
            self.index_progress.setValue(self.index_progress.maximum())
            path = self.index_job.get_path()
            if not self.directories.findItems(path, Qt.MatchExactly):
                self.directories.addItem(path)
            self.indexing_stopped()


class SearcherWidget(QWidget):
    def __init__(self, wheres_the_fck_receipt: api_interface.WheresTheFckReceipt, parent=None):
        QWidget.__init__(self, parent)
        self.wheres_the_fck_receipt = wheres_the_fck_receipt  # type: api_interface.WheresTheFckReceipt

        # query
        self.query = QLineEdit()
        self.query.returnPressed.connect(self.search_button_clicked)
        self.limit_box = QSpinBox()
        self.limit_box.setValue(0)
        search_button = QPushButton('Search')
        search_button.clicked.connect(self.search_button_clicked)

        query_bar_layout = QHBoxLayout()
        query_bar_layout.setContentsMargins(0, 0, 0, 0)
        query_bar_layout.addWidget(QLabel("Search Term"))
        query_bar_layout.addWidget(self.query)
        query_bar_layout.addWidget(QLabel("Max. Results"))
        query_bar_layout.addWidget(self.limit_box)
        query_bar_layout.addWidget(search_button)

        # the file_list
        self.match_list = QTableWidget()
        self.match_list.setShowGrid(True)
        self.match_list.setAutoScroll(True)
        self.match_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.match_list.itemSelectionChanged.connect(self.match_list_item_selection_changed)

        self.preview = QLabel()
        preview_layout = QHBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(self.match_list)
        preview_layout.addWidget(self.preview)
        preview_widget = QWidget()
        preview_widget.setLayout(preview_layout)

        # my layout
        layout = QVBoxLayout()
        layout.addLayout(query_bar_layout)
        layout.addWidget(preview_widget)
        self.setLayout(layout)

    def match_list_item_selection_changed(self):
        curr_row = self.match_list.currentRow()
        # todo

    def search_button_clicked(self):
        matches = self.wheres_the_fck_receipt.search(self.query.text(), self.limit_box.value())
        self.match_list.clear()
        self.match_list.setColumnCount(2)
        self.match_list.setHorizontalHeaderLabels(['Path', 'Text'])
        header = self.match_list.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.match_list.setRowCount(len(matches))
        for i in range(len(matches)):
            result = matches[i]
            self.match_list.setItem(i, 0, QTableWidgetItem(result.get_path()))
            self.match_list.setItem(i, 1, QTableWidgetItem(result.get_text()))

        self.query.setFocus()
        self.query.selectAll()


class WheresTheFckReceipt(QMainWindow):

    def __init__(self, wheres_the_fck_receipt: api_interface.WheresTheFckReceipt, parent=None):
        QWidget.__init__(self, parent=None)
        self.wheres_the_fck_receipt = wheres_the_fck_receipt

        # tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(Indexer(wheres_the_fck_receipt), "Indexer")
        self.tab_widget.addTab(SearcherWidget(wheres_the_fck_receipt), "Searcher")


        # build window title
        app_context = ApplicationContext()
        version = app_context.build_settings['version']
        app_name = app_context.build_settings['app_name']
        window_title = app_name + " v" + version

        # get settings
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QCoreApplication.setApplicationName(app_name)

        settings = QSettings()
        # build main window
        self.setWindowTitle(window_title)
        self.setCentralWidget(self.tab_widget)
        self.resize(800, 600)
