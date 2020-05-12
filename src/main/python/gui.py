import os
import sqlite3
import sys
import abc
import time

import cv2
from PyQt5 import QtGui, QtWidgets

from PyQt5.QtCore import QDateTime, QStandardPaths, QFile, QFileInfo, Qt, QObject, QThread, pyqtSignal, QTimer
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
        self.index_job_timer = QTimer()
        self.index_job_timer.timeout.connect(self.index_job_timer_timeout)

        # add dir button
        self.add_directory = QPushButton('Add Directory')
        self.add_directory.setEnabled(True)
        self.add_directory.clicked.connect(self.add_directory_clicked)

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
        self.index_console = QTextEdit()
        self.index_console.setReadOnly(True)

        # layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Indexed Directories:"))
        layout.addWidget(self.add_directory)
        layout.addWidget(self.directories)
        layout.addWidget(file_list_action_bar_widget)
        layout.addWidget(index_status_widget)
        layout.addWidget(self.index_console)
        self.setLayout(layout)

    def add_directory_clicked(self):
        directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        if directory:
            self.index_job = self.wheres_the_fck_receipt.add_directory(directory)
            self.index_job.start()
            self.index_job_timer.start(500)

    def index_job_timer_timeout(self):
        self.index_status.setText(self.index_job.get_status())


class WheresTheFckReceipt(QMainWindow):

    def __init__(self, wheres_the_fck_receipt: api_interface.WheresTheFckReceipt, parent=None):
        QWidget.__init__(self, parent=None)
        self.wheres_the_fck_receipt = wheres_the_fck_receipt

        # tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(Indexer(wheres_the_fck_receipt), "Indexer")

        # build window title
        app_context = ApplicationContext()
        version = app_context.build_settings['version']
        app_name = app_context.build_settings['app_name']
        window_title = app_name + " v" + version

        # build main window
        self.setWindowTitle(window_title)
        self.setCentralWidget(self.tab_widget)
        self.resize(800, 600)
