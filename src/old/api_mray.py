# MRAY THINGS
import subprocess

from old import api2
import keyboard
import logging
import threading

import win32api, win32con, win32gui, win32ui


def get_window_handle(name):
    top_windows = []
    win32gui.EnumWindows(windowEnumerationHandler, top_windows)
    for i in top_windows:
        if name.lower() in i[1].lower():
            return i[0]
    return None


def set_always_on_top(name):
    hwnd = get_window_handle(name)
    if hwnd is not None:
        # logging.getLogger(__name__).info("making {} the always on top window".format(name))
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)


# noinspection PyBroadException
def sendkey_to_mray_window(key):
    hwnd = get_window_handle("mray client")

    temp = win32api.SendMessage(hwnd, win32con.WM_CHAR, key, 0)
    logging.getLogger(__name__).debug(temp)


def sendkey_if_mray_is_in_foreground(key):
    try:
        fg_window_name = win32gui.GetWindowText(win32gui.GetForegroundWindow()).lower()
        if "mray client" in fg_window_name:
            keyboard.press_and_release(key)
    except Exception as e:
        logging.getLogger(__name__).exception(str(e))


def make_mray_foreground_window():
    try:
        hwnd = get_window_handle("mray client")
        if hwnd is not None:
            win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        logging.getLogger(__name__).exception(str(e))


def windowEnumerationHandler(hwnd, top_windows):
    top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))


def mray_is_open():
    hwnd = get_window_handle("mray client")
    if hwnd is not None:
        return True
    return False


def start_mray_and_wait(wait=True):
    if not mray_is_open():
        cmd = '"C:\\Program Files\\mRayClient\\bin\\mRayClient.exe" --hotkey'
        subprocess.Popen(cmd)

        if wait:
            input("Please press a key ...")


class MrayGestureControl(api2.CamAppModule):

    def __init__(self, window_name, config: api2.ProjectConfig):
        self.window_name = window_name
        self.clear_observations = config.clear_observations
        self.min_observations = config.min_observations
        self.key_names = config.key_names
        self.keras_cv_model = api2.create_class_instance("api", config.model_name)
        self.keras_cv_model.init(config.image_size, config.class_names, config.channels)
        self.keras_cv_model.create_and_load_weights(config.model_path, True)
        self.bounding_box = config.bounding_box
        self.mode_names = config.mode_names
        self.mode_keys = config.mode_keys
        self.mode_change_class = config.mode_change_class
        self.mode_up_class = config.mode_up_class
        self.mode_down_class = config.mode_down_class
        self.use_modes = config.use_modes
        self.draw_scale = config.draw_scale
        self.use_desktop_painter = config.use_desktop_painter
        self.draw_only_mode_on_desktop = config.draw_only_mode_on_desktop
        self.draw_text_on_video = config.draw_text_on_video
        self.video_window_on_top = config.video_window_on_top

        # state
        self.observations = []
        self.current_mode_idx = 0

    def process_frame(self, frame, working_frame):
        if self.video_window_on_top:
            set_always_on_top(self.window_name)

        # make prediction
        text = ""
        if self.use_modes:
            text = text + "" + self.mode_names[self.current_mode_idx] + " - "

        cls_idx, cls = self.keras_cv_model.predict(working_frame, None)
        if cls_idx >= 0:
            self.observations.append(cls_idx)
            text = text + "" + cls
            if len(self.observations) > self.min_observations:
                self.observations.pop(0)

            color = (255, 0, 0)
            obs_count = self.observations.count(cls_idx)
            if obs_count > self.min_observations * 1.0 / 3.0:
                color = (255, 255, 0)
            if obs_count > self.min_observations * 2.0 / 3.0:
                color = (0, 255, 0)

            # minimum number of observations reached
            if self.observations.count(cls_idx) == self.min_observations:
                key = self.key_names[cls_idx]

                # in check if we use modes
                if self.use_modes:
                    if cls == self.mode_change_class:
                        self.current_mode_idx = self.current_mode_idx + 1
                        if self.current_mode_idx >= len(self.mode_names):
                            self.current_mode_idx = 0
                        key = None
                    elif cls == self.mode_up_class:
                        key = self.mode_keys[self.current_mode_idx][0]
                    elif cls == self.mode_down_class:
                        key = self.mode_keys[self.current_mode_idx][1]

                # send key if we have one
                if key:
                    # text = text + ", key: " + str(key)
                    # make_mray_foreground_window()
                    sendkey_if_mray_is_in_foreground(key)

                # clear observations
                clear_observations = self.clear_observations[cls_idx]
                if clear_observations == -1:
                    self.observations = []
                elif clear_observations > 0:
                    target_size = len(self.observations) - clear_observations
                    while len(self.observations) > target_size:
                        self.observations.pop(0)

        if self.draw_text_on_video:
            frame = api2.draw_text(frame.copy(), text, scale=self.draw_scale)

        if self.use_desktop_painter:
            if self.draw_only_mode_on_desktop and self.use_modes:
                text = self.mode_names[self.current_mode_idx]
                color = (0, 255, 0)
            DesktopPainter.show(text, color)
        return frame, working_frame


class DesktopPainter:
    text = ""
    current_thread = None
    main_thread_id = None
    wndClassAtom = None
    hWindow = None
    fontSize = 25
    color = (0, 255, 0)

    @staticmethod
    def stop_thread_if_running():
        if (DesktopPainter.current_thread is not None):
            win32api.PostThreadMessage(DesktopPainter.main_thread_id, win32con.WM_QUIT, 0, 0)
            DesktopPainter.current_thread.join()
            DesktopPainter.current_thread = None
            DesktopPainter.main_thread_id = None

    @staticmethod
    def show(text, color):
        DesktopPainter.text = text
        DesktopPainter.color = color

        if not DesktopPainter.current_thread:
            DesktopPainter.current_thread = threading.Thread(target=DesktopPainter.create_win)
            DesktopPainter.current_thread.start()

        win32gui.RedrawWindow(DesktopPainter.hWindow, None, None, win32con.RDW_INVALIDATE | win32con.RDW_ERASE)

    @staticmethod
    def create_win():
        DesktopPainter.main_thread_id = win32api.GetCurrentThreadId()
        hInstance = win32api.GetModuleHandle()
        className = 'MyWindowClassName'

        # http://msdn.microsoft.com/en-us/library/windows/desktop/ms633576(v=vs.85).aspx
        # win32gui does not support WNDCLASSEX.
        wndClass = win32gui.WNDCLASS()
        # http://msdn.microsoft.com/en-us/library/windows/desktop/ff729176(v=vs.85).aspx
        wndClass.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
        wndClass.lpfnWndProc = DesktopPainter.wndProc
        wndClass.hInstance = hInstance
        wndClass.hCursor = win32gui.LoadCursor(None, win32con.IDC_ARROW)
        wndClass.hbrBackground = win32gui.GetStockObject(win32con.WHITE_BRUSH)
        wndClass.lpszClassName = className
        # win32gui does not support RegisterClassEx
        if DesktopPainter.wndClassAtom is None:
            DesktopPainter.wndClassAtom = win32gui.RegisterClass(wndClass)

        # http://msdn.microsoft.com/en-us/library/windows/desktop/ff700543(v=vs.85).aspx
        # Consider using: WS_EX_COMPOSITED, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_TRANSPARENT
        # The WS_EX_TRANSPARENT flag makes events (like mouse clicks) fall through the window.
        exStyle = win32con.WS_EX_COMPOSITED | win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOPMOST | win32con.WS_EX_TRANSPARENT

        # http://msdn.microsoft.com/en-us/library/windows/desktop/ms632600(v=vs.85).aspx
        # Consider using: WS_DISABLED, WS_POPUP, WS_VISIBLE
        style = win32con.WS_DISABLED | win32con.WS_POPUP | win32con.WS_VISIBLE

        # http://msdn.microsoft.com/en-us/library/windows/desktop/ms632680(v=vs.85).aspx
        DesktopPainter.hWindow = win32gui.CreateWindowEx(
            exStyle,
            DesktopPainter.wndClassAtom,
            None,  # WindowName
            style,
            0,  # x
            0,  # y
            win32api.GetSystemMetrics(win32con.SM_CXSCREEN),  # width
            win32api.GetSystemMetrics(win32con.SM_CYSCREEN),  # height
            None,  # hWndParent
            None,  # hMenu
            hInstance,
            None  # lpParam
        )

        # http://msdn.microsoft.com/en-us/library/windows/desktop/ms633540(v=vs.85).aspx
        win32gui.SetLayeredWindowAttributes(DesktopPainter.hWindow, 0x00ffffff, 255,
                                            win32con.LWA_COLORKEY | win32con.LWA_ALPHA)

        # http://msdn.microsoft.com/en-us/library/windows/desktop/dd145167(v=vs.85).aspx
        # win32gui.UpdateWindow(hWindow)

        # http://msdn.microsoft.com/en-us/library/windows/desktop/ms633545(v=vs.85).aspx
        win32gui.SetWindowPos(DesktopPainter.hWindow, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOACTIVATE | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)

        # http://msdn.microsoft.com/en-us/library/windows/desktop/ms633548(v=vs.85).aspx
        # win32gui.ShowWindow(hWindow, win32con.SW_SHOW)

        win32gui.PumpMessages()

    @staticmethod
    def wndProc(hWnd, message, wParam, lParam):
        if message == win32con.WM_PAINT:
            hdc, paintStruct = win32gui.BeginPaint(hWnd)

            dpiScale = win32ui.GetDeviceCaps(hdc, win32con.LOGPIXELSX) / 60.0
            # http://msdn.microsoft.com/en-us/library/windows/desktop/dd145037(v=vs.85).aspx
            lf = win32gui.LOGFONT()
            lf.lfFaceName = "Verdana"
            lf.lfHeight = int(round(dpiScale * DesktopPainter.fontSize))
            # lf.lfWeight = 150
            # Use nonantialiased to remove the white edges around the text.
            # lf.lfQuality = win32con.NONANTIALIASED_QUALITY
            hf = win32gui.CreateFontIndirect(lf)
            win32gui.SelectObject(hdc, hf)

            rect = win32gui.GetClientRect(hWnd)
            win32gui.SetTextColor(hdc, win32api.RGB(*DesktopPainter.color))
            # http://msdn.microsoft.com/en-us/library/windows/desktop/dd162498(v=vs.85).aspx
            win32gui.DrawText(
                hdc,
                DesktopPainter.text,
                -1,
                rect,
                win32con.DT_LEFT | win32con.DT_NOCLIP | win32con.DT_SINGLELINE | win32con.DT_VCENTER
            )
            # win32gui.Rectangle(hdc, 100,100, 300,300)
            win32gui.EndPaint(hWnd, paintStruct)
            return 0

        elif message == win32con.WM_DESTROY:
            print('Closing the window.')
            win32gui.PostQuitMessage(0)
            return 0

        else:
            return win32gui.DefWindowProc(hWnd, message, wParam, lParam)
