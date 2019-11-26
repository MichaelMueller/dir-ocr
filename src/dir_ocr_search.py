import argparse
import api

# args
parser = argparse.ArgumentParser(description='dir_ocr_search')
parser.add_argument('index_path', type=str, help='the index path')
parser.add_argument('--query_string', type=str, default=None, help='the query string')
parser.add_argument('--num_docs', type=int, default=3, help='the maximum number of docs returned')
args = parser.parse_args()

dir_ocr = api.DirOcr()
if args.query_string is None:
    query_str = input("query_string: ")
else:
    query_str = args.query_string
dir_ocr.search(args.index_path, query_str, args.num_docs)
