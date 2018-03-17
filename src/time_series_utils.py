#!/usr/bin/python

import os
import logging
import shutil

def createCleanDir(dirName):
    if not os.path.isdir(dirName):
        os.mkdir(dirName)
    else:
        logging.info("Cleaning up old {} directory".format(dirName))
        shutil.rmtree(dirName)
        os.mkdir(dirName)


