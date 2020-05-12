import traceback

import api
import sys

if __name__ == '__main__':
    app_controller = api.AppController()
    ret_code = app_controller.start()

    sys.exit(ret_code)
