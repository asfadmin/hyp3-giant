#!/usr/bin/python

import os
import zipfile
import glob
import argparse
import logging
import shutil

#
#  Unzip any files found in path1 that aren't already in path2
#  Note that it is assumed that zip files contain directories!
#

def unzipFiles(path1,path2):
    logging.info("Unzipping files in {} into {}".format(path1,path2))
    for myfile in glob.glob("{}/*.zip".format(path1)):
        newDir = myfile.replace(".zip","")
        if not os.path.isdir(os.path.join(path2,os.path.basename(newDir))):
            logging.info("    unzipping file {}".format(myfile))
            zip_ref = zipfile.ZipFile(myfile,'r')            
            
            # Look for a directory in the zip file
            found_dir = False
            
            for f in zip_ref.namelist():
                if '/' in f:
                    found_dir = True
            
            # If no directory is found, create one
            path = os.path.join(path2,os.path.basename(newDir))
            if not found_dir:
                path = os.path.join(path2,os.path.basename(newDir))
                logging.info( "    creating directory {}".format(path))
                os.makedirs(path)
                zip_ref.extractall(path)
            else:
                zip_ref.extractall(path2)

            zip_ref.close()

            # Fix old phase file names
            if (len(glob.glob("{}/*_unw_phase.tif".format(path)))==0 and 
                len(glob.glob("{}/*_unwrapped.tif".format(path)))==0):
                logging.debug("        found directory {} with no unwrapped phase files".format(path))
                back = os.getcwd()
                os.chdir(path)
                for myfile in glob.glob("????????_????????_phase.tif"):
                    newname = myfile.replace("phase.tif","unw_phase.tif")
                    logging.info("        renaming file {} to {}".format(myfile,newname))
                    shutil.move(myfile,newname) 
                os.chdir(back)
        else:
            logging.info("    skipping file {}".format(myfile))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="unzipFiles.pt",description="Unzip all files from path1 into path2")
    parser.add_argument("path1",help="Path to input zip files")
    parser.add_argument("path2",help="Path to place output files")
    args = parser.parse_args()

    logFile = "unzipping_log.txt"
    logging.basicConfig(filename=logFile,format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler())

    logging.info("Starting run")

    unzipFiles(args.path1,args.path2)
