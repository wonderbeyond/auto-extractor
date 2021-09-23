import traceback
import time
import os
import re
import argparse
import threading
import queue
import zipfile

import chardet
import inotify.adapters

ZIP_FILENAME_UTF8_FLAG = 0x800


def do_unzip(filename):
    try:
        zf = zipfile.ZipFile(filename)
    except FileNotFoundError:
        return
    namelist = zf.namelist()
    top_dirs = set(n.split(os.sep)[0] for n in namelist)

    if len(top_dirs) == 1:
        has_top_dir = True
    else:
        has_top_dir = False

    fixed_top_dir = os.path.splitext(
        os.path.basename(filename)
    )[0] if not has_top_dir else ""

    extract_target = os.path.join(
        os.path.dirname(filename),
        fixed_top_dir
    )
    print(f"Generating {extract_target}")

    def extractall(zfile: zipfile.ZipFile, target):
        """
        Reference: https://stackoverflow.com/questions/37723505/namelist-from-zipfile-returns-strings-with-an-invalid-encoding
        """
        for info in zfile.infolist():
            filename = info.filename
            if info.flag_bits & ZIP_FILENAME_UTF8_FLAG == 0:
                filename_bytes = filename.encode('cp437')
                guessed_encoding = chardet.detect(filename_bytes)['encoding'] or 'GB18030'
                filename = filename_bytes.decode(guessed_encoding, errors='replace')
                info.filename = filename
            print(f" * writing {filename}")
            zfile.extract(info, path=target)

    extractall(zfile=zf, target=extract_target)


def unzip_worker(q):
    fetched_items = set()
    fetched_count = 0

    while True:
        time.sleep(0.1)
        fetched_count += 1
        try:
            fetched_items.add(q.get(block=False))
            q.task_done()
        except queue.Empty:
            continue

        if fetched_count >= 5:
            fetched_count = 0  # reset batch process flag
            for item in fetched_items:
                print(f'Unpacking {item} ...')
                try:
                    do_unzip(item)
                except Exception:
                    traceback.print_exc()
            fetched_items.clear()
            time.sleep(0.25)


def main():
    parser = argparse.ArgumentParser(
        description='Watch and unzip.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-d', '--target-directory', dest='path', type=str, default='.')
    parser.add_argument('-x', '--ignore-regex', dest='ignore_regex', nargs="+", default=[])
    args = parser.parse_args()

    ignore_re_patterns = [re.compile(e) for e in args.ignore_regex]

    print(f"Start watching {os.path.abspath(args.path)} ...")
    i = inotify.adapters.InotifyTree(args.path)
    q = queue.Queue()

    threading.Thread(target=unzip_worker, args=[q]).start()

    for event in i.event_gen(yield_nones=False):
        _, type_names, path, filename = event
        types_set = set(type_names)
        abs_filepath = os.path.join(path, filename)

        if any(p.search(abs_filepath) for p in ignore_re_patterns):
            continue

        if (
            filename and filename.lower().endswith(".zip")
            and types_set & {"IN_MOVED_TO", "IN_CLOSE_WRITE"}
        ):
            q.put(abs_filepath)


if __name__ == '__main__':
    main()
