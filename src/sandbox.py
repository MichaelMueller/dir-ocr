from old import api2

project_conf = api2.ProjectConfig()
project_conf.to_json_file("../project.json")

# import sys
# from os import path
#
# import cv2
# import numpy as np
#
# from PyQt5 import QtCore
# from PyQt5 import QtWidgets
# from PyQt5 import QtGui
#
#
# class RecordVideo(QtCore.QObject):
#     image_data = QtCore.pyqtSignal(np.ndarray)
#
#     def __init__(self, camera_port=1, parent=None):
#         super().__init__(parent)
#         self.camera = cv2.VideoCapture(camera_port)
#         self.timer = QtCore.QBasicTimer()
#
#     def start_recording(self):
#         self.timer.start(0, self)
#
#     def timerEvent(self, event):
#         if event.timerId() != self.timer.timerId():
#             return
#
#         read, data = self.camera.read()
#         if read:
#             self.image_data.emit(data)
#
#
# class ImageWidget(QtWidgets.QWidget):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.image = QtGui.QImage()
#         self._red = (0, 0, 255)
#         self._width = 2
#         self._min_size = (30, 30)
#
#     def image_data_slot(self, image_data):
#         self.image = self.get_qimage(image_data)
#         if self.image.size() != self.size():
#             self.setFixedSize(self.image.size())
#
#         self.update()
#
#     def get_qimage(self, image: np.ndarray):
#         height, width, colors = image.shape
#         bytesPerLine = 3 * width
#         QImage = QtGui.QImage
#
#         image = QImage(image.data,
#                        width,
#                        height,
#                        bytesPerLine,
#                        QImage.Format_RGB888)
#         image = image.scaledToWidth(320)
#         image = image.rgbSwapped()
#         return image
#
#     def paintEvent(self, event):
#         painter = QtGui.QPainter(self)
#         painter.drawImage(0, 0, self.image)
#         self.image = QtGui.QImage()
#
#
# class MainWidget(QtWidgets.QWidget):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.image_widget = ImageWidget()
#
#         # TODO: set video port
#         self.record_video = RecordVideo()
#
#         image_data_slot = self.image_widget.image_data_slot
#         self.record_video.image_data.connect(image_data_slot)
#
#         layout = QtWidgets.QVBoxLayout()
#
#         layout.addWidget(self.image_widget)
#         self.run_button = QtWidgets.QPushButton('Start')
#         layout.addWidget(self.run_button)
#
#         self.run_button.clicked.connect(self.record_video.start_recording)
#         self.setLayout(layout)
#
#
# def main():
#     app = QtWidgets.QApplication(sys.argv)
#
#     main_window = QtWidgets.QMainWindow(None, QtCore.Qt.WindowStaysOnTopHint)
#     main_widget = MainWidget()
#     main_window.setCentralWidget(main_widget)
#     main_window.show()
#     sys.exit(app.exec_())
#
#
# if __name__ == '__main__':
#     main()

# import cv2
#
# import api
# import shutil
# import logging
# import keyboard
# from time import sleep
# api.setup_logging()
# logger = logging.getLogger(__name__)
#
# # for file_path in api.process_dir("C:/Users/mueller/Desktop/git/mray_gesture_control/var/hands-data/background_thumb_up_down_ok_fist/val"):
# #     file_path_new = file_path.replace(".thumb.", ".thumb_up.")
# #     logger.info("moving {} to {}".format(file_path, file_path_new))
# #     shutil.move(file_path, file_path_new)
#
# # if api.mray_is_open() == False:
# #     api.start_mray_and_wait(True)
# # #print("bringing to foreground")
# # #api.bring_mray_to_foreground()
# # sleep(5)
# # for i in range(20):
# #     api.sendkey_if_mray_is_in_foreground("a")
# #     sleep(1)
# # for i in range(20):
# #     api.sendkey_if_mray_is_in_foreground("s")
# #     sleep(1)
#
# # image_size = 64
# # channels = 3
# # model_file = api.get_model_file_path("..\\var\\hands-data\\hands_test", "unet", image_size, [])
# # model = api.create_unet(model_file, image_size, channels)
# #
# # for file_path in api.process_dir("..\\var\\hands-data\\hands_test\\val", api.common_image_file_extensions):
# #     _, _, _, is_mask, _ = api.get_img_info(file_path)
# #     if not is_mask:
# #         _, img_with_overlay = api.unet_segment(cv2.imread(file_path), model, image_size, channels)
# #         cv2.imshow("Output", img_with_overlay)
# #         cv2.waitKey(0)
#
# # config = api.Config()
# # # options
# # config.model_dir = None
# # config.image_size = None
# # config.class_names = []
# # config.key_names = []
# # config.classifier_name = None
# # config.cam = 0
# # config.width = None
# # config.height = None
# # config.exposure = None
# # config.to_json_file("../mray_gesture_control.json")
#
# for file_path in api.process_dir("..\\var\\hands-data\\background.wipe_left.wipe_right.wipe_up.wipe_down.ok.fist\\train3", api.common_image_file_extensions):
#     name, cls, cls_name, is_mask, is_augmented, is_color_mask, ext = api.CnnClassifier.get_img_info(file_path)
#
#     img = cv2.imread(file_path)
#     api.CnnClassifier.save_img(img, "..\\var\\hands-data\\background.wipe_left.wipe_right.wipe_up.wipe_down.ok.fist\\train", cls, cls_name, is_mask, is_augmented, is_color_mask, ext)
#
#
#
