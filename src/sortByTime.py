#!/usr/bin/python

import glob
import os
import shutil
import logging
from time_series_utils import *

def getTimes(path,filelist,filetype):
    newlist = []
    times = [] 
    for myfile in filelist: 
        if ".zip" in myfile or os.path.isdir(os.path.join(path,myfile)):       
            try:
                if filetype == 'rtc':
                    dt = os.path.basename(myfile).split("_")[4]
                elif filetype == 'insar':
                    if myfile.startswith("S1A_") or myfile.startswith("S1B_"):
                        dt = os.path.basename(myfile).split("_")[1]
                    else:
                        dt = os.path.basename(myfile).split("-")[1]
                else:
                    logging.error("ERROR: Unknown type of file {}".format(filetype))
                    mexit(1)
                time = dt.split("T")[1]
                times.append(time)
                newlist.append(myfile)
            except:
                logging.info("Warning: Unable to determine date for file {}; ignoring".format(myfile))
        # We have a regular file; not a dir or zip
        else:
            logging.info("Not a zip file or directory - {} - ignoring".format(myfile))

    return newlist, times

def sortByTime(path,filelist,filetype):
    logging.info("Sorting files by time")
    logging.info("Got files {}".format(filelist))
    newlist, times = getTimes(path,filelist,filetype)
    logging.info("Got times {}".format(times))
    classes = []
    lists = []
    max_classes = 0
    for i in range(len(newlist)):
        placed = False
        for j in range(len(classes)):
            if abs(int(times[i])-int(classes[j])) < 9:
                lists[j].append(newlist[i])
                placed = True
                break
        if not placed:
            max_classes = max_classes+1
            classes.append(times[i])
            namelist = []
            lists.append(namelist)
            lists[max_classes-1].append(newlist[i])

    for i in range(len(classes)):
        logging.info("Class {} : {} contains".format(i,classes[i]))
        for j in range(len(lists[i])):
            logging.info("    {}".format(os.path.basename(lists[i][j])))

    for i in range(len(classes)):
        time = classes[i]
        mydir = "sorted_{}".format(time)
        logging.info("Making clean directory {}".format(mydir))
        createCleanDir(mydir)
        for myfile in lists[i]:
            newfile = os.path.join(mydir,os.path.basename(myfile))
            logging.info("Linking file {} to {}".format(os.path.join(path,myfile),newfile))
            os.symlink(os.path.join(path,myfile),newfile)

    logging.info("Done sorting files by time")
    return classes, lists

if __name__ == "__main__":


    logFile = "sorting_log.txt"
    logging.basicConfig(filename=logFile,format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler())

    print "\n"
    logging.info("Starting run")
    print " "

    filelist = glob.glob("*.zip")
    filetype = "insar"
    path = "."
    sortByTime(path,filelist,filetype)

