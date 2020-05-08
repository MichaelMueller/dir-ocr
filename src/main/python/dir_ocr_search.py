import argparse
import api
import logging

# args
parser = argparse.ArgumentParser(description='dir_ocr_search')
parser.add_argument('index_path', type=str, help='the index path')
parser.add_argument('--query_string', type=str, default=None, help='the query string')
parser.add_argument('--num_docs', type=int, default=None, help='the maximum number of docs returned')
parser.add_argument('--log_level', type=int, default=logging.INFO, help='the log level')
parser.add_argument('--log_file', type=str, default=None, help='the log file')

args = parser.parse_args()
api.setup_logging(args.log_level, args.log_file)

dir_ocr = api.DirOcr()
if args.query_string is None:
    dir_ocr.interactive_search(args.index_path, args.num_docs)
else:
    dir_ocr.search(args.index_path, args.query_string, args.num_docs)
