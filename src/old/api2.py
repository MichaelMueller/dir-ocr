import json
import logging
import os
import sys
from abc import abstractmethod
from time import time
from collections import Counter

import cv2
import keras
import keras.backend as K
import numpy
import numpy as np
from keras.applications import VGG16, InceptionV3
from keras.callbacks import ModelCheckpoint, EarlyStopping
from keras.layers import Dense, Flatten, Conv2D, MaxPooling2D, Input, UpSampling2D
from keras.layers import Dropout
from keras.layers.merge import concatenate
from keras.models import Model
from keras.models import Sequential
from keras.optimizers import Adam
from keras.utils import to_categorical

# VARS
common_image_file_extensions = ["png", "bmp", "jpeg", "jpg"]


# FUNCTIONS
def process_dir(start_dir, extensions=None):
    if extensions is None:
        extensions = []
    for root, dirs, files in os.walk(start_dir):
        for basename in files:
            file_name, ext = os.path.splitext(basename)
            ext = ext[1:].lower()
            if len(extensions) > 0 and ext not in extensions:
                continue
            path = os.path.join(root, basename)
            yield path


def image_resize(image, width=None, height=None, inter=cv2.INTER_AREA):
    # initialize the dimensions of the image to be resized and
    # grab the image size
    dim = None
    (h, w) = image.shape[:2]

    # if both the width and height are None, then return the
    # original image
    if width is None and height is None:
        return image

    # check to see if the width is None
    if width is None:
        # calculate the ratio of the height and construct the
        # dimensions
        r = height / float(h)
        dim = (int(w * r), height)

    # otherwise, the height is None
    else:
        # calculate the ratio of the width and construct the
        # dimensions
        r = width / float(w)
        dim = (width, int(h * r))

    # resize the image
    resized = cv2.resize(image, dim, interpolation=inter)

    # return the resized image
    return resized


def setup_logging(log_level=logging.INFO, log_file=None):
    class InfoFilter(logging.Filter):
        def filter(self, rec):
            return rec.levelno in (logging.DEBUG, logging.INFO, logging.WARNING)

    h1 = logging.StreamHandler(sys.stdout)
    h1.setLevel(logging.DEBUG)
    h1.addFilter(InfoFilter())
    h2 = logging.StreamHandler(sys.stderr)
    h2.setLevel(logging.ERROR)

    handlers = [h1, h2]
    kwargs = {"format": "%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
              "datefmt": '%Y-%m-%d:%H:%M:%S', "level": log_level}

    if log_file:
        h1 = logging.FileHandler(filename=log_file)
        h1.setLevel(logging.DEBUG)
        handlers = [h1]

    kwargs["handlers"] = handlers
    logging.basicConfig(**kwargs)


def draw_text(img, text, bg_color=(255, 255, 255), scale=0.5):
    font_face = cv2.QT_FONT_NORMAL
    color = (0, 0, 0)
    thickness = cv2.FILLED
    margin = 5

    while True:
        (label_width, label_height), baseline = cv2.getTextSize(text, font_face, scale, thickness)
        if label_width + margin > img.shape[1]:
            scale -= 0.05
        else:
            break

    pos = (0, 0)
    end_y = pos[1] + label_height + baseline + margin

    cv2.rectangle(img, pos, (img.shape[1] - 1, end_y), bg_color, thickness)
    cv2.putText(img, text, (0 + margin, end_y - margin), font_face, scale, color, 1, cv2.LINE_AA)
    return img


def create_class_instance(module_name, class_name):
    module = __import__(module_name)
    class_ = getattr(module, class_name)
    instance = class_()
    return instance


def get_function(module_name, func_name):
    module = __import__(module_name)
    func_ = getattr(module, func_name)
    return func_


class Config:

    def __init__(self):
        pass

    def to_json_file(self, json_file):
        with open(json_file, 'w') as out_file:
            out_file.write(self.to_json())

    def from_json_file(self, json_file):
        with open(json_file) as in_file:
            json_data = json.load(in_file)
            self.from_json(json_data)

    def to_json(self):
        data = self.__dict__
        return json.dumps(data, indent=4)

    def from_json(self, data):
        for key, val in data.items():
            self.__dict__[key] = val


class ProjectConfig(Config):

    def __init__(self):
        super().__init__()

        # basic params (video)
        self.action = None
        self.class_names = []
        self.cam = 0
        self.width = None
        self.height = None
        self.exposure = None
        self.flip = None
        self.record_timeout = 0.5
        self.log_level = logging.INFO
        self.log_file = None
        self.bounding_box = None
        self.video_backend = 0
        self.fps = None
        self.record_dir = None
        self.draw_scale = 1.0

        # recorder and model params
        self.image_dirs = []
        self.test_image_dirs = None
        self.image_size = 224
        self.model_name = "Vgg16"
        self.channels = 3
        self.model_path = None
        self.batch_size = 32
        self.num_epochs = 32
        self.display_width = None
        self.display_height = None

        # gesture control
        self.key_names = []  # one per class
        self.clear_observations = []  # one per class
        self.icons = []  # one per class
        self.action_labels = []  # one per class
        self.min_observations = 14
        self.mode_names = None
        self.mode_keys = None
        self.mode_change_class = None
        self.mode_up_class = None
        self.mode_down_class = None
        self.use_modes = False
        self.use_desktop_painter = False
        self.font_size = 20
        self.draw_only_mode_on_desktop = True
        self.draw_text_on_video = True
        self.video_window_on_top = True

class CamAppModule:

    def __init__(self):
        pass

    def process_frame(self, frame, working_frame):
        return None

    def process_key(self, key):
        pass


class CamApp:

    def __init__(self, cam=0, width=None, height=None, exposure=None, fps=None, video_backend=0):
        self.window_name = "CamApp"
        self.window_flag = cv2.WINDOW_AUTOSIZE
        self.cam = cam
        self.exposure = exposure
        self.width = width
        self.height = height
        self.wait_key_secs = 2
        self.modules = []  # type: List[CamAppModule]
        self.show_frame = True
        self.exit_key = 27
        self.fps = fps
        self.video_backend = video_backend

    def __call__(self):

        # cam settings
        if self.video_backend is not None:
            cap = cv2.VideoCapture(self.cam, self.video_backend)
        else:
            cap = cv2.VideoCapture(self.cam)

        if self.width is not None and self.height is not None:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if self.fps is not None:
            cap.set(cv2.CAP_PROP_FPS, self.fps)
        if self.exposure is not None:
            cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)

        if self.show_frame:
            cv2.namedWindow(self.window_name, self.window_flag)
        try:

            stop = False
            while not stop:
                # read frame
                _, frame = cap.read()

                # process frame
                working_frame = frame.copy()
                for module in self.modules:
                    frame, working_frame = module.process_frame(frame, working_frame)

                if self.show_frame:
                    # show frame
                    cv2.imshow(self.window_name, frame)

                # process keys
                key = cv2.waitKeyEx(self.wait_key_secs)
                # potentially stop
                if self.exit_key is not None and key == self.exit_key:
                    stop = True
                elif cv2.getWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE) < 1:
                    stop = True
                else:
                    # run key processor
                    for module in self.modules:
                        module.process_key(key)

        finally:
            cap.release()
            cv2.destroyAllWindows()


class CnnClassifier:

    def __init__(self):
        self.image_size = None
        self.class_names = None
        self.channels = None
        self.scale_divisor = 255.0
        self.default_ext = "png"
        self.use_checkpoints = True
        self.use_early_stopping = True
        self.early_stopping_min_delta = 0.001
        self.early_stopping_patience = 3
        self.verbose = 1

        # state
        self.model = None
        self.model_file = None
        self.monitor_target = None
        self.monitor_mode = None

    def init(self, image_size, class_names, channels=3):
        self.image_size = image_size
        self.class_names = class_names
        self.channels = channels

    @abstractmethod
    def create(self) -> keras.models.Model:
        return None, None, None

    def get_model_file_path(self, model_dir):
        basename = "{}.{}.{}.hdf5".format(self.__class__.__name__, self.image_size, self.channels)
        return os.path.join(model_dir, basename)

    @staticmethod
    def save_img(img, save_dir, cls_idx, cls_name, ext):
        logger = logging.getLogger(__name__)

        i = 0
        while True:
            i = i + 1
            file_basename = "{}.{}.{}.{}".format(i, cls_idx, cls_name, ext)
            file_path = os.path.join(save_dir, file_basename)
            if not os.path.exists(file_path):
                if not os.path.isdir(save_dir):
                    os.makedirs(save_dir)
                logger.info("saving image to {}".format(file_path))
                cv2.imwrite(file_path, img)
                break

    @staticmethod
    def get_img_info(file_path):
        # should be "name.cls_idx.cls_name.ext"
        parts = os.path.basename(file_path).split(".")

        assert len(parts) == 4  # at least name and ext should be left
        name = parts[0]
        cls = parts[1]
        cls_name = parts[2]
        ext = parts[3]
        return name, cls, cls_name, ext

    def prepare_image(self, img):

        # resize
        if img.shape[1] != self.image_size or img.shape[0] != self.image_size:
            img = cv2.resize(img, (self.image_size, self.image_size))

        # color conversion
        if self.channels == 3 and (len(img.shape) < 2 or img.shape[2] == 1):
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif self.channels == 1 and len(img.shape) > 2 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # rescale (also the masks if necessary)
        if self.scale_divisor is not None:
            img = img / self.scale_divisor

        return img

    def load_and_prepare_image(self, file_path):
        img = cv2.imread(file_path)
        return self.prepare_image(img)

    def create_and_load_weights(self, model_path, force_load=False):
        if self.model is not None:
            return

        # create model
        self.model, self.monitor_target, self.monitor_mode = self.create()

        # get the model file
        self.model_file = model_path

        # load weights if necessary
        if os.path.exists(self.model_file) or force_load:
            self.model.load_weights(self.model_file)

    def train_in_memory(self, model_path, inputs, outputs, validation_data=None, num_epochs=8, batch_size=32):
        # create model
        self.create_and_load_weights(model_path)
        model = self.model

        # make callbacks
        callbacks = []
        if self.use_checkpoints:
            model_checkpoint = ModelCheckpoint(filepath=self.model_file, save_best_only=True,
                                               monitor=self.monitor_target,
                                               mode=self.monitor_mode)
            callbacks.append(model_checkpoint)

        if self.use_early_stopping:
            early_stopping = EarlyStopping(monitor=self.monitor_target,
                                           min_delta=self.early_stopping_min_delta,
                                           patience=self.early_stopping_patience,
                                           verbose=self.verbose,
                                           mode=self.monitor_mode)
            callbacks.append(early_stopping)

        # start training
        model.fit(inputs, outputs, epochs=num_epochs, batch_size=batch_size, validation_data=validation_data,
                  verbose=self.verbose, callbacks=callbacks)

        model_file_dir = os.path.dirname(self.model_file)
        if not os.path.isdir(model_file_dir):
            os.makedirs(model_file_dir)
        model.save_weights(self.model_file)

    def train(self, model_path, image_dirs, test_image_dirs=None, num_epochs=8, batch_size=32):
        logger = logging.getLogger(__name__)

        # load data
        # load train data and prepare
        x_train, y_train = self.load_data(image_dirs)
        logger.info(x_train.shape)
        logger.info(y_train.shape)

        validation_data = None
        if test_image_dirs is not None:
            x_test, y_test = self.load_data(test_image_dirs)
            logger.info(x_test.shape)
            logger.info(y_test.shape)
            validation_data = (x_test, y_test)

        self.train_in_memory(model_path, x_train, y_train, validation_data, num_epochs, batch_size)

    def load_data(self, image_dirs):
        logger = logging.getLogger(__name__)
        images = []
        labels = []

        for image_dir in image_dirs:
            for file_path in process_dir(image_dir, common_image_file_extensions):
                name, cls, cls_name, ext = CnnClassifier.get_img_info(file_path)
                if cls_name in self.class_names:
                    images.append(self.load_and_prepare_image(file_path))
                    labels.append(cls)
                else:
                    logger.warning("class {} not found in classes. skipping image {}".format(cls_name, file_path))

        unique_labels = Counter(labels).keys()  # equals to list(set(words))
        images_per_label = Counter(labels).values()  # counts the elements' frequency
        logger.info("found classes {} with images {}".format(str(unique_labels), str(images_per_label)))

        images = np.array(images)
        # convert to numpy arrays and select the correct output
        outputs = to_categorical(np.array(labels))
        return images, outputs

    def predict(self, img, model_dir):
        # create and load model
        self.create_and_load_weights(model_dir, True)
        model = self.model
        # make prediction
        predictions = model.predict(numpy.array([self.prepare_image(img)]))
        cls_idx = numpy.argmax(predictions[0])
        cls = self.class_names[cls_idx]

        return cls_idx, cls


class Vgg16(CnnClassifier):

    def create(self) -> keras.models.Model:
        vgg_base = VGG16(weights='imagenet', include_top=False,
                         input_shape=(self.image_size, self.image_size, self.channels))

        base_model = vgg_base  # Topless
        # Add top layer
        x = base_model.output
        x = Flatten()(x)
        x = Dense(128, activation='relu', name='fc1')(x)
        x = Dense(128, activation='relu', name='fc2')(x)
        x = Dense(128, activation='relu', name='fc3')(x)
        x = Dropout(0.5)(x)
        x = Dense(64, activation='relu', name='fc4')(x)
        predictions = Dense(len(self.class_names), activation='softmax')(x)

        model = Model(inputs=base_model.input, outputs=predictions)

        # Train top layers only
        for layer in base_model.layers:
            layer.trainable = False

        model.compile(optimizer='Adam', loss='categorical_crossentropy', metrics=['accuracy'])
        return model, "acc", "max"


class InceptionV3(CnnClassifier):

    def create(self) -> keras.models.Model:
        vgg_base = keras.applications.InceptionV3(weights='imagenet', include_top=False,
                                                  input_shape=(self.image_size, self.image_size, self.channels))

        base_model = vgg_base  # Topless
        # Add top layer
        x = base_model.output
        x = Flatten()(x)
        x = Dense(128, activation='relu', name='fc1')(x)
        x = Dense(128, activation='relu', name='fc2')(x)
        x = Dense(128, activation='relu', name='fc3')(x)
        x = Dropout(0.5)(x)
        x = Dense(64, activation='relu', name='fc4')(x)
        predictions = Dense(len(self.class_names), activation='softmax')(x)

        model = Model(inputs=base_model.input, outputs=predictions)

        # Train top layers only
        for layer in base_model.layers:
            layer.trainable = False
        adam_opt = Adam(lr=0.0001)
        model.compile(optimizer=adam_opt, loss='categorical_crossentropy', metrics=['accuracy'])
        return model, "acc", "max"


class DefaultCnnClassifier(CnnClassifier):
    def create(self) -> keras.models.Model:
        logger = logging.getLogger(__name__)

        model = Sequential()
        model.add(Conv2D(32, (3, 3), padding='same', activation='relu',
                         input_shape=(self.image_size, self.image_size, self.channels)))
        model.add(Conv2D(32, (3, 3), activation='relu'))
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Dropout(0.25))

        model.add(Conv2D(64, (3, 3), padding='same', activation='relu'))
        model.add(Conv2D(64, (3, 3), activation='relu'))
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Dropout(0.25))

        model.add(Conv2D(64, (3, 3), padding='same', activation='relu'))
        model.add(Conv2D(64, (3, 3), activation='relu'))
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Dropout(0.25))

        model.add(Flatten())
        model.add(Dense(512, activation='relu'))
        model.add(Dropout(0.5))

        model.add(Dense(len(self.class_names), activation='softmax'))
        model.compile(optimizer=Adam(), loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        if len(self.class_names) > 1:
            logger.info("More than one class found. Building multi class network")
            model.add(Dense(len(self.class_names), activation='softmax'))
            model.compile(optimizer=Adam(), loss='categorical_crossentropy', metrics=['accuracy'])
        else:
            logger.info("one class found. Building single class network")
            model.add(Dense(1, kernel_initializer='normal', activation='sigmoid'))
            model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])

        logger.info(model.summary())
        return model, "acc", "max"


class ManualRecorder(CamAppModule):

    def __init__(self, class_names, save_dir, timeout=1):
        self.class_names = class_names
        self.save_dir = save_dir
        self.timeout = timeout

        # state
        self.recording = False
        self.curr_cls_idx = 0
        self.curr_cls = self.class_names[self.curr_cls_idx]
        self.last_save_time = time()

    def process_frame(self, frame, working_frame):
        help_text = "current class: {}, recording: {}, press ESC to exit, c to switch class, SPACE to toggle recording".format(
            self.curr_cls, str(self.recording))
        frame = draw_text(frame, help_text)

        # save image if we have a timeout
        if self.recording:
            seconds_elapsed = time() - self.last_save_time
            if seconds_elapsed >= self.timeout:
                CnnClassifier.save_img(working_frame, self.save_dir, self.curr_cls_idx, self.curr_cls, "png")
                self.last_save_time = time()
        return frame, working_frame

    def process_key(self, key):
        # logging.getLogger(__name__).info(key)
        if key is ord(' '):
            self.recording = not self.recording
        elif key is ord('c'):
            self.curr_cls_idx += 1
            if self.curr_cls_idx >= len(self.class_names):
                self.curr_cls_idx = 0
            self.curr_cls = self.class_names[self.curr_cls_idx]


class ImageResizer(CamAppModule):

    def __init__(self, target_width, target_height=None, use_frame=True, use_working_frame=False):
        self.target_width = target_width
        self.target_height = target_height
        self.inter = cv2.INTER_AREA
        self.use_frame = use_frame
        self.use_working_frame = use_working_frame

    def process_frame(self, frame, working_frame):
        if self.target_width is not None or self.target_height is not None:
            if self.use_frame:
                frame = image_resize(frame, self.target_width, self.target_height, self.inter)
            if self.use_working_frame:
                working_frame = image_resize(working_frame, self.target_width, self.target_height, self.inter)
        return frame, working_frame


class ImageFlipper(CamAppModule):

    def __init__(self, flip=1, use_frame=True, use_working_frame=False):
        self.flip = flip
        self.use_frame = use_frame
        self.use_working_frame = use_working_frame

    def process_frame(self, frame, working_frame):
        if self.flip is not None:
            if self.use_frame:
                frame = cv2.flip(frame, self.flip)
            if self.use_working_frame:
                working_frame = cv2.flip(working_frame, self.flip)
        return frame, working_frame


class BoundingBoxExtractor(CamAppModule):

    def __init__(self, bounding_box_size=None, frame_idx=0, frame_bb_output_index=1):
        self.bounding_box_size = bounding_box_size
        self.frame_idx = frame_idx
        self.frame_bb_output_index = frame_bb_output_index

    def process_frame(self, frame, working_frame):
        if self.bounding_box_size:
            im_h, im_w = frame.shape[:2]
            w = self.bounding_box_size * im_w
            h = self.bounding_box_size * im_w
            x = round((im_w / 2.0) - w / 2.0)
            y = round((im_h / 2.0) - h / 2.0)
            w = round(w)
            h = round(h)
            bb = x, y, w, h

            frame = cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
            working_frame = working_frame[bb[1]:bb[1] + bb[3], bb[0]:bb[0] + bb[2]]

        return frame, working_frame


class VideoInference(CamAppModule):

    def __init__(self, model_path, image_size, model_name, class_names, channels, bounding_box):
        self.keras_cv_model = create_class_instance("api", model_name)
        self.keras_cv_model.init(image_size, class_names, channels)
        self.keras_cv_model.create_and_load_weights(model_path, True)
        self.bounding_box = bounding_box

    def process_frame(self, frame, working_frame):
        # make prediction
        currentText = "Undefined class"

        cls_idx, cls = self.keras_cv_model.predict(working_frame, None)
        if cls_idx >= 0:
            currentText = "Detected as " + cls + " !!! "

        frame = draw_text(frame, currentText)
        return frame, working_frame
