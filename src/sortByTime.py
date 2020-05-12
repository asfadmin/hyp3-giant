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
        if ".zip" in myfile or "vsis3" in myfile or os.path.isdir(os.path.join(path,myfile)):       
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
            logging.info("Not a zip file, directory, or aws file - {} - ignoring".format(myfile))

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
            hour = int(times[i][0:2])
            min = int(times[i][2:4])
            sec = int(times[i][4:6])
            secofday = (((hour*60)+min)*60)+sec 

            chour = int(classes[j][0:2])
            cmin = int(classes[j][2:4])
            csec = int(classes[j][4:6])
            csecofday = (((chour*60)+cmin)*60)+csec 
            
            if (abs(csecofday-secofday)%86400) < 11:
                if filetype == "rtc":
                    if ("S1A" in newlist[i] and "S1A" in lists[j][0]):
                        lists[j].append(newlist[i])
                        placed = True
                    elif ("S1B" in newlist[i] and "S1B" in lists[j][0]):
                        lists[j].append(newlist[i])
                        placed = True
                else:
                    lists[j].append(newlist[i])
                    placed = True
                if placed:
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

    # The following won't work for AWS files, but is required for INSAR time series!
    if filetype == 'insar':
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

    logging.info("Starting run")

    filelist = glob.glob("*.zip")
    filetype = "rtc"
    path = "."
    sortByTime(path,filelist,filetype)

