#!/usr/bin/python
# encoding: utf-8
# download_products.py
# Rohan Weeden
# Created: June 16, 2017

# User script for automatically downloading products.
# Useful for downloading large quantity of products as they take a long time
# to download.

from asf_hyp3 import API
try:
    import curses
except:
    pass
import os
import requests
import sys
import time
import threading
import argparse


def download_products(
                        api,
                        directory="hyp3-products/",
                        id=None,
                        sub_id=None,
                        sub_name=None,
                        creation_date=None,
                        verbose=True,
                        threads=0):
    try:
        product_list = api.get_products(id, sub_id=sub_id, sub_name=sub_name, creation_date=creation_date)
    except requests.ConnectionError:
        if verbose:
            print("Could not connect to the api")
        return
    # Check that the api call succeeded
    if 'message' in product_list:
        return product_list['message']

    ###################################
    # Define Helper functions/classes #
    ###################################

    # Downloading without progress tracking
    def download(url, out_name):
        resp = requests.get(url, stream=True)
        with open(out_name, 'wb') as out_f:
            out_f.write(resp.content)

    # Download with progress tracking
    def download_with_progress(url, out_name, bar):
        if bar is not None:
            bar.download(url, out_name)
        elif sys.stdout.isatty():
            # If curses is available on this platform, use it for clearing
            # the terminal
            try:
                curses.setupterm()
                bar = CursesBar()
            except NameError:
                # If Windows, we're out of luck... No progress tracking
                if os.name == 'nt':
                    download(url, out_name)
                    return
                else:
                    bar = AsciiBar()
            download_with_progress(url, out_name, bar)
        else:
            download(url, out_name)
        return bar

    # Progress bar template
    class DownloadBar(object):
        def __init__(self):
            self.bar_length = 50
            self.bar_template = "|{}{}| {}% "
            pass

        def download(self, url, out_name):
            resp = requests.get(url, stream=True)
            self.size = int(resp.headers['content-length'])
            with open(out_name, 'wb') as out_f:
                self.done = 0
                for data in resp.iter_content(chunk_size=4096):
                    out_f.write(data)
                    self.done += len(data)
                    self.progress = int(self.bar_length * self.done / self.size)
                    # Clear the bar
                    self.clear()
                    sys.stdout.write(self.bar_template.format("█" * self.progress, " " * (self.bar_length - self.progress), 100 * self.done / self.size))
                    sys.stdout.flush()

    # Progress bar using curses function for clearing and getting terminal size
    class CursesBar(DownloadBar):
        def __init__(self):
            try:
                # Python 3
                super().__init__()
            except:
                # Python 2
                super(CursesBar, self).__init__()
            self.bar_length = curses.tigetnum('cols') - 15

        def clear(self):
            sys.stdout.write(str(curses.tigetstr('cr')) + str(curses.tigetstr('el')))

    # Progress bar using basic terminal. Does not work correctly on windows
    class AsciiBar(DownloadBar):
        def clear(self):
            sys.stdout.write("\r")

    class DownloadThread(threading.Thread):
        def __init__(self, url, out_name):
            super(DownloadThread, self).__init__()
            self._stop_event = threading.Event()
            self.url = url
            self.out_name = out_name

        def stop(self):
            self._stop_event.set()

        def stopped(self):
            return self._stop_event.is_set()

        def run(self):
            resp = requests.get(self.url, stream=True)
            with open(self.out_name, 'wb') as out_f:
                for data in resp.iter_content(chunk_size=4096):
                    if self.stopped():
                        out_f.close()
                        os.remove(self.out_name)
                        break
                    out_f.write(data)

    ###################################
    #  End Helper functions/classes   #
    ###################################

    # Create the download directory
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Check each product and download it if it doesnt exist already
    failed_products = 0
    total_products = 0
    active_threads = 0
    threads_list = [None] * threads
    thread_index = 0
    bar = None
    for product in product_list:
        name = product['name']
        # Check if it has already been downloaded
        file_name = os.path.join(directory, name)
        if not os.path.isfile(file_name):
            if verbose:
                print("Getting new product: {}".format(name))
            try:
                total_products += 1
                # Check if a thread slot is available and we are using threads
                if threads > 0 and active_threads < threads:
                    # Fire off a new download thread
                    threads_list[thread_index] = DownloadThread(product['url'], file_name)
                    threads_list[thread_index].start()
                    thread_index = (thread_index + 1) % threads
                    active_threads += 1
                    # Check if thread slots are full
                    if active_threads == threads:
                        try:
                            # wait for the first thread to complete
                            while threads_list[thread_index].isAlive():
                                time.sleep(0.05)
                                thread_index = (thread_index + 1) % threads
                        except KeyboardInterrupt:
                            for t in threads_list:
                                if t.isAlive():
                                    t.stop()
                                    failed_products += 1
                            if verbose:
                                print("")
                            break
                        active_threads -= 1
                else:
                    if verbose:
                        bar = download_with_progress(product['url'], file_name, bar)
                        print("Done")
                    else:
                        download(product['url'], file_name)
            except KeyboardInterrupt:
                if verbose:
                    print("Failed")
                failed_products += 1
                if os.path.isfile(file_name):
                    os.remove(file_name)
                if verbose:
                    print("")
                break
            except requests.ConnectionError:
                if verbose:
                    print("Failed")
                failed_products += 1
                if os.path.isfile(file_name):
                    os.remove(file_name)
    if verbose:
        print("Attempted to download {} products: {} succeeded, {} failed".format(total_products, total_products - failed_products, failed_products))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="download_products.py",description="Download HYP3 products")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-s","--sub_name",help="Name of the subscription to download")
    group.add_argument("-i","--id",help="ID of the subscription to download")
    group.add_argument("-d","--date",help="Date of the subscription to download")

    args = parser.parse_args()

    print("Username: ")
    try:
        username = input()
    except:
        username = raw_input()

    print "Username is {}".format(username)
    api = API(username)
    api.login()

    download_products(
                        api,
                        directory="hyp3-products/",
                        id=None,
                        sub_id=args.id,
                        sub_name=args.sub_name,
                        creation_date=args.date,
                        verbose=True,
                        threads=0)
#    download_products(api)
