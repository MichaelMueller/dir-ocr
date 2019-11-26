import argparse
import api

# args
parser = argparse.ArgumentParser(description='dir_ocr_index')
parser.add_argument('directory', type=str, help='the input directory')
parser.add_argument('index_path', type=str, help='the index path')
parser.add_argument('--rebuild', action="store_true", help='whether to rebuild the index')
parser.add_argument('--text_extract_library', type=str, default="textract", help='the library used for text extract (tesseract/textract)')
args = parser.parse_args()

dir_ocr = api.DirOcr()
dir_ocr.index(args.directory, args.index_path, args.rebuild, args.text_extract_library)
