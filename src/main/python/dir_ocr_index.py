import argparse
import api
import logging
# args
parser = argparse.ArgumentParser(description='dir_ocr_index')
parser.add_argument('directory', type=str, help='the input directory')
parser.add_argument('index_path', type=str, help='the index path')
parser.add_argument('--rebuild', action="store_true", help='whether to rebuild the index')
parser.add_argument('--log_level', type=int, default=logging.INFO, help='the log level')
parser.add_argument('--log_file', type=str, default=None, help='the log file')

args = parser.parse_args()
api.setup_logging(args.log_level, args.log_file)

dir_ocr = api.DirOcr()
dir_ocr.index(args.directory, args.index_path, args.rebuild)
