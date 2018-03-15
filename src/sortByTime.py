#!/usr/bin/python

import glob
import os
import shutil

def getTimes(filelist,filetype):
    times = [] 
    for myfile in filelist: 
        if filetype == 'rtc':
            dt = myfile.split("_")[4]
        elif filetype == 'insar':
            dt = myfile.split("-")[1]
        else:
            print "ERROR: Unknown type of file {}".format(filetype)
            exit(1)
        time = dt.split("T")[1]
        times.append(time)
    return times

def sortByTime(filelist,filetype):
    print "got files {}".format(filelist)
    times = getTimes(filelist,filetype)
    print "got times {}".format(times)
    classes = []
    lists = []
    max_classes = 0
    for i in range(len(filelist)):
        print "Placing file {}".format(filelist[i])
        placed = False
        for j in range(len(classes)):
            if abs(int(times[i])-int(classes[j])) < 9:
                lists[j].append(filelist[i])
                placed = True
                break
        if not placed:
            max_classes = max_classes+1
            classes.append(times[i])
            namelist = []
            lists.append(namelist)
            lists[max_classes-1].append(filelist[i])

    for i in range(len(classes)):
        print "Class {} : {} contains".format(i,classes[i])
        for j in range(len(lists[i])):
            print "    {}".format(lists[i][j])

    for i in range(len(classes)):
        time = classes[i]
        mydir = "sorted_{}".format(time)
        if not os.path.isdir(mydir):
            print "Making directory {}".format(mydir)
            os.mkdir(mydir)
        for myfile in lists[i]:
            print "Moving file {} to {}".format(myfile,mydir)
            shutil.move(myfile,mydir)

    return classes, lists

if __name__ == "__main__":

   filelist = glob.glob("*.zip")
   sortByTime(filelist)

