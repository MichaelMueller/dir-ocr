import traceback

from fbs_runtime.application_context.PyQt5 import ApplicationContext

import api
import gui
import sys

if __name__ == '__main__':
    # run the application
    app_context = ApplicationContext()
    wheres_the_fck_receipt = gui.WheresTheFckReceipt(api.WheresTheFckReceipt())
    wheres_the_fck_receipt.show()
    exit_code = app_context.app.exec_()  # 2. Invoke app_context.app.exec_()
    sys.exit(exit_code)
