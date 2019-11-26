from old import api2, api_mray


def record(config: api2.ProjectConfig):
    cam_app = api2.CamApp(config.cam, config.width, config.height, config.exposure, config.fps, config.video_backend)
    image_flipper = api2.ImageFlipper(config.flip, use_frame=True, use_working_frame=True)
    bounding_box_extractor = api2.BoundingBoxExtractor(config.bounding_box)
    image_resizer = api2.ImageResizer(config.display_width, config.display_height, use_frame=True,
                                      use_working_frame=False)
    manual_recorder = api2.ManualRecorder(config.class_names, config.record_dir, config.record_timeout)

    cam_app.modules.append(image_flipper)
    cam_app.modules.append(bounding_box_extractor)
    cam_app.modules.append(image_resizer)
    cam_app.modules.append(manual_recorder)
    cam_app()


def train(config: api2.ProjectConfig):
    keras_cv_model = api2.create_class_instance("api", config.model_name)
    keras_cv_model.use_early_stopping = False
    keras_cv_model.init(config.image_size, config.class_names, config.channels)
    keras_cv_model.train(config.model_path, config.image_dirs, config.test_image_dirs, config.num_epochs,
                         config.batch_size)


def test(config: api2.ProjectConfig):
    image_flipper = api2.ImageFlipper(config.flip, use_frame=True, use_working_frame=True)
    bounding_box_extractor = api2.BoundingBoxExtractor(config.bounding_box)
    image_resizer = api2.ImageResizer(config.display_width, config.display_height, use_frame=True,
                                      use_working_frame=False)
    video_inference = api2.VideoInference(config.model_path, config.image_size, config.model_name, config.class_names,
                                          config.channels, config.bounding_box)

    cam_app = api2.CamApp(config.cam, config.width, config.height, config.exposure, config.fps, config.video_backend)
    cam_app.modules.append(image_flipper)
    cam_app.modules.append(bounding_box_extractor)
    cam_app.modules.append(image_resizer)
    cam_app.modules.append(video_inference)
    cam_app()


def run(config: api2.ProjectConfig):
    api_mray.start_mray_and_wait()

    cam_app = api2.CamApp(config.cam, config.width, config.height, config.exposure, config.fps, config.video_backend)
    image_flipper = api2.ImageFlipper(config.flip, use_frame=True, use_working_frame=True)
    bounding_box_extractor = api2.BoundingBoxExtractor(config.bounding_box)
    image_resizer = api2.ImageResizer(config.display_width, config.display_height, use_frame=True,
                                      use_working_frame=False)
    mray_gesture_control = api_mray.MrayGestureControl(cam_app.window_name, config)

    cam_app.modules.append(image_flipper)
    cam_app.modules.append(bounding_box_extractor)
    cam_app.modules.append(image_resizer)
    cam_app.modules.append(mray_gesture_control)

    # run
    if config.use_desktop_painter:
        api_mray.DesktopPainter.fontSize = config.font_size
    api_mray.make_mray_foreground_window()
    cam_app()

    if config.use_desktop_painter:
        api_mray.DesktopPainter.stop_thread_if_running()
