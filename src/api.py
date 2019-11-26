import abc
import os
import shutil
from typing import List, Optional
from pdf2image import convert_from_path
from PIL import Image
from pytesseract import pytesseract
import textract
import hashlib
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID
import sys
from whoosh.qparser import QueryParser
from whoosh import scoring

def sha256_sum(file_path):
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(file_path, 'rb', buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


class FileProcessor:
    @abc.abstractmethod
    def process(self, full_path, basename, file_name, ext):
        pass


class TextProcessor:
    @abc.abstractmethod
    def process(self, text, full_path, basename, file_name, ext):
        pass


class DirParser:
    def __init__(self, directory, file_processor, extensions=[]):
        self.directory = directory  # type: Optional[str]
        self.file_processor = file_processor  # type: FileProcessor
        self.extensions = extensions  # type: List[Optional[str]]

    def run(self):
        for root, dirs, files in os.walk(self.directory):
            for basename in files:
                file_name, ext = os.path.splitext(basename)
                ext = ext[1:].lower()
                if len(self.extensions) > 0 and ext not in self.extensions:
                    continue
                path = os.path.join(root, basename)

                self.file_processor.process(path, basename, file_name, ext)


class TextractProcessor(FileProcessor):
    def __init__(self, text_processor):
        self.text_processor = text_processor  # type: TextProcessor

    def process(self, full_path, basename, file_name, ext):
        try:
            text = textract.process(full_path)
            self.text_processor.process(text.decode('unicode_escape'), full_path, basename, file_name, ext)
        except Exception as e:
            print("error processing file {}: {}".format(full_path, str(e)))



class TesseractProcessor(FileProcessor):
    def __init__(self, text_processor):
        self.text_processor = text_processor  # type: TextProcessor

    def process(self, full_path, basename, file_name, ext):
        if ext == "pdf":
            images = convert_from_path(full_path)
        else:
            images = [Image.open(full_path)]

        text = ""
        for image in images:
            text = text + pytesseract.image_to_string(image)
        print(text)
        self.text_processor.process(text, full_path, basename, file_name, ext)


class WhooshIndexer(TextProcessor):
    def __init__(self, index_path, rebuild):
        self.index_path = index_path
        self.rebuild = rebuild
        self.ix = None

    def process(self, text, full_path, basename, file_name, ext):
        sha256 = sha256_sum(full_path)
        self.assert_index_writer()
        print("indexing file {} with sha256 {}".format(full_path, sha256))
        self.ix.add_document(title=basename, path=full_path, file_id=sha256, content=text, textdata=text)

    def assert_index_writer(self):
        if self.ix is not None:
            return

        if self.rebuild and os.path.exists(self.index_path):
            print("deleting index at {}".format(self.index_path))
            shutil.rmtree(self.index_path)

        if os.path.exists(self.index_path):
            self.ix = open_dir(self.index_path).writer()
        else:
            os.makedirs(self.index_path, 0o777, True)
            schema = Schema(title=TEXT(stored=True), path=TEXT(stored=True), file_id=ID(stored=True), content=TEXT, textdata=TEXT(stored=True))
            ix = create_in(self.index_path, schema)
            self.ix = ix.writer()

    def __del__(self):
        if self.ix:
            self.ix.commit()

class DirOcr:

    def index(self, directory, index_path, rebuild, text_extract_library):
        whoosh_indexer = WhooshIndexer(index_path, rebuild)

        if text_extract_library == "tesseract":
            file_processor = TesseractProcessor(whoosh_indexer)
            extensions = ["png", "jpg", "jpeg", "pdf"]
        else:
            file_processor = TextractProcessor(whoosh_indexer)
            extensions = []

        dir_parser = DirParser(directory, file_processor, extensions)

        dir_parser.run()

    def search(self, index_path, query_str, num_docs):
        ix = open_dir(index_path)

        with ix.searcher(weighting=scoring.Frequency) as searcher:
            query = QueryParser("content", ix.schema).parse(query_str)
            results = searcher.search(query, limit=num_docs)
            if len(results) > 0:
                for i in range(0, len(results)):
                    print(str(results[i].score), results[i]['title'], results[i]['path'])
            else:
                print("NO RESULTS!!!")