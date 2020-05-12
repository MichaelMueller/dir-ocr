import traceback

from PyQt5.QtCore import QFileInfo, QStandardPaths
from fbs_runtime.application_context.PyQt5 import ApplicationContext

import api_interface
import api
import gui
import sys


class AppDataDirPath(api_interface.AppDataDirPath):

    def get(self) -> str:
        db_path = QFileInfo(
            QStandardPaths.writableLocation(QStandardPaths.DataLocation) + "/" + ApplicationContext().build_settings[
                'app_name'])
        return db_path.absoluteFilePath()


if __name__ == '__main__':
    # run the application
    app_context = ApplicationContext()
    delete_db = "--delete_db" in sys.argv
    db_factory = api.DbFactory(AppDataDirPath(), delete_db)
    index_job_factory = api.IndexJobFactory()
    wheres_the_fck_receipt = gui.WheresTheFckReceipt(api.WheresTheFckReceipt(db_factory, index_job_factory))
    wheres_the_fck_receipt.show()
    exit_code = app_context.app.exec_()  # 2. Invoke app_context.app.exec_()
    sys.exit(exit_code)
