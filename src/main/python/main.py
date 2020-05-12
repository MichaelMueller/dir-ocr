import traceback

import api
import sys

if __name__ == '__main__':
    ret_code = -1
    try:
        app_controller = api.AppController()
        ret_code = app_controller.start()
    except Exception as e:
        print(traceback.format_exception(*sys.exc_info()))

    sys.exit(ret_code)
