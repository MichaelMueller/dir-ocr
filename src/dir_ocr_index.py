import argparse
import api

# args
parser = argparse.ArgumentParser(description='dir_ocr_index')
parser.add_argument('directory', type=str, help='the input directory')
parser.add_argument('index_path', type=str, help='the index path')
parser.add_argument('--rebuild', action="store_true", help='whether to rebuild the index')

args = parser.parse_args()

dir_ocr = api.DirOcr()
dir_ocr.index(args.directory, args.index_path, args.rebuild)
