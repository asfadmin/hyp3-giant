#!/usr/bin/python

import os
import zipfile
import glob
import argparse

#
#  Unzip any files found in path1 that aren't already in path2
#  Note that it is assumed that zip files contain directories!
#

def unzipFiles(path1,path2):
    print "Unzipping files in {} into {}".format(path1,path2)
    for myfile in glob.glob("{}/*.zip".format(path1)):
        newDir = myfile.replace(".zip","")
        if not os.path.isdir(os.path.join(path2,os.path.basename(newDir))):
            print("    unzipping file {}".format(myfile))
            zip_ref = zipfile.ZipFile(myfile,'r')
            zip_ref.extractall(path2)
            zip_ref.close()
        else:
            print("    skipping file {}".format(myfile))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="unzipFiles.pt",description="Unzip all files from path1 into path2")
    parser.add_argument("path1",help="Path to input zip files")
    parser.add_argument("path2",help="Path to place output files")
    args = parser.parse_args()

    unzipFiles(args.path1,args.path2)
