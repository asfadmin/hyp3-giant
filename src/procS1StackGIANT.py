#!/usr/bin/env python
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
###############################################################################
# procS1StackGIANT.py
#
# Project:  APD HYP3
# Purpose:  Create INSAR time series outputs from GIAnT 
#  
# Author:   Tom Logan
#
# Issues/Caveats:
#
###############################################################################
# Copyright (c) 2018, Alaska Satellite Facility
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
# 
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
###############################################################################
import os
import argparse
import shutil
import zipfile
import glob
from getParameter import getParameter
from osgeo import gdal
from cutGeotiffs import cutFiles
from execute import execute
import saa_func_lib as saa
import numpy as np
import makePNG
import h5py
from aps_weather_model import aps_weather_model
from asf_hyp3 import API
from os.path import expanduser
from download_products import download_products
from getUsernamePassword import getUsernamePassword
from sortByTime import sortByTime 
from unzipFiles import unzipFiles
from osgeo.gdalconst import *
import logging
import configparser
from time_series_utils import *

def prepareHypFiles(path,hyp):
    hypDir = "HYP"
    createCleanDir(hypDir)

    if path is None:
        tmpPath = "."
    else:
        tmpPath = path

    dir_cnt = 0
    for myfile in os.listdir(tmpPath):
        if path is not None:
            myfile = os.path.join(path,myfile)
        testName = os.path.join(path,myfile)
        if os.path.isdir(testName) and (len(glob.glob("{}/*_unw_phase.tif".format(testName)))>0 or len(glob.glob("{}/*_unwrapped.tif".format(testName)))>0):
            linkFile = os.path.join(hypDir,os.path.basename(myfile))
            if not os.path.exists(linkFile):
                os.symlink(testName,linkFile)
            dir_cnt = dir_cnt + 1

    if dir_cnt == 0:
        logging.error("ERROR: Unable to find any direcories in {}".format(tmpPath))
        exit(1)
        
    os.chdir(hypDir)

    unw_cnt = len(glob.glob("*/*_unw_phase.tif"))
    cor_cnt = len(glob.glob("*/*_corr.tif"))

    old_coh = False
    if cor_cnt == 0:
        cor_cnt = len(glob.glob("*/*_coh.tif"))
        if cor_cnt != 0:
            old_coh = True         

    old_snap = False
    if unw_cnt == 0:
        unw_cnt = len(glob.glob("*/*_unwrapped.tif"))
        if unw_cnt != 0:
            old_snap = True

    if unw_cnt != cor_cnt:
        logging.error("ERROR: You are missing files!!! unw_cnt = %s; cor_cnt = %s" % (unw_cnt,cor_cnt))
        exit(1)

    f = open('../igram_list.txt','w')
    if old_snap:
        ext = "_unwrapped.tif"
    else:
        ext = "_unw_phase.tif"

    for myfile in glob.glob("*/*{}".format(ext)):
        logging.debug("Checking file {}".format(myfile))
        mdate = os.path.basename(myfile).split("_")[0]
        sdate = os.path.basename(myfile).split("_")[1]

        # Catch the case of S1TBX names
        if not len(mdate)==15 and not len(mdate)==8:
            logging.debug("mdate is not a date or date time {}; reparsing".format(mdate))
            mdate = os.path.basename(myfile.split("_")[5])
            sdate = myfile.split("_")[6]
            
        pFile = os.path.basename(myfile)
	if not old_coh:
            cFile = os.path.basename(myfile.replace(ext,"_corr.tif"))
        else:
            cFile = os.path.basename(myfile.replace(ext,"_coh.tif"))
        txtFile = glob.glob("{}/*20*_20*.txt".format(os.path.dirname(myfile)))[0]
        baseline = getParameter(txtFile,"Baseline")
        f.write("{} {} {} {} {}\n".format(mdate,sdate,pFile,cFile,baseline))

    # Older zipfiles don't unzip into their own directory!
    for myfile in glob.glob("*{}".format(ext)):
        mdate = myfile.split("_")[0]
        sdate = myfile.split("_")[1]
        pFile = myfile
        cFile = myfile.replace(ext,"_corr.tif")
        txtFile = myfile.replace(ext,".txt")
        baseline = getParameter(txtFile,"Baseline")
        f.write("{} {} {} {} {}\n".format(mdate,sdate,pFile,cFile,baseline))

    f.close()

    os.chdir("..")
    createCleanDir("DATA")
    os.chdir("DATA")
    for myfile in glob.glob("../{}/*/*{}".format(hypDir,ext)):
         if not os.path.exists(os.path.basename(myfile)):
             os.symlink(myfile,os.path.basename(myfile))
    if not old_coh:
        for myfile in glob.glob("../{}/*/*_corr.tif".format(hypDir)):
             if not os.path.exists(os.path.basename(myfile)):
                 os.symlink(myfile,os.path.basename(myfile))
    else:
        for myfile in glob.glob("../{}/*/*_coh.tif".format(hypDir)):
             if not os.path.exists(os.path.basename(myfile)):
                 os.symlink(myfile,os.path.basename(myfile))


    # Older zipfiles don't unzip into their own directory!
    for myfile in glob.glob("../{}/*_unw_phase.tif".format(hypDir)):
        if not os.path.exists(os.path.basename(myfile)):
            os.symlink(myfile,os.path.basename(myfile))
    for myfile in glob.glob("../{}/*_corr.tif".format(hypDir)):
        if not os.path.exists(os.path.basename(myfile)):
            os.symlink(myfile,os.path.basename(myfile))

    os.chdir("..") 

    return('igram_list.txt',hypDir) 


def getFileList(descFile):
    params = {} 
    params['mdate'] = []
    params['sdate'] = []
    params['pFile'] = []
    params['cFile'] = []
    params['basel'] = []

    with open(descFile) as f:
        content = f.readlines()
        for item in content:
            if len(item.strip())!=0:
                params['mdate'].append(item.split()[0])
                params['sdate'].append(item.split()[1])
                params['pFile'].append(item.split()[2])
                params['cFile'].append(item.split()[3])
                params['basel'].append(item.split()[4])

    return(params)

def resizeFiles(params):
    x,y,trans,proj = saa.read_gdal_file_geo(saa.open_gdal_file(params['pFile'][0]))
    if x>4096 or y>4096:
        if x > y:
            width = 4096
            height = 0
        else:
            width = 0
            height = 4096
 
        for i in range(len(params['mdate'])):
            outFile = params['pFile'][i].replace(".tif","_resize.tif")
            logging.info("    processing file {} to create file {}".format(params['pFile'][i],outFile))
            gdal.Translate(outFile,params['pFile'][i],resampleAlg=GRIORA_Cubic,width=width,height=height)
            params['pFile'][i] = outFile

            outFile = params['cFile'][i].replace(".tif","_resize.tif")
            logging.info("    processing file {} to create file {}".format(params['cFile'][i],outFile))
            gdal.Translate(outFile,params['cFile'][i],resampleAlg=GRIORA_Cubic,width=width,height=height)
            params['cFile'][i] = outFile


def reprojectFiles(params):
    os.chdir("DATA") 
    for i in range(len(params['mdate'])):
        x,y,trans,proj = saa.read_gdal_file_geo(saa.open_gdal_file(params['pFile'][i]))
        if "PROJCS" in proj:
            outFile = params['pFile'][i].replace(".tif","_wgs84.tif")
            logging.info("    processing file {} to create file {}".format(params['pFile'][i],outFile))
            gdal.Warp(outFile,params['pFile'][i],dstSRS="EPSG:4326")
            params['pFile'][i] = outFile
            outFile = params['cFile'][i].replace(".tif","_wgs84.tif")
            logging.info("    processing file {} to create file {}".format(params['cFile'][i],outFile))
            gdal.Warp(outFile,params['cFile'][i],dstSRS="EPSG:4326")
            params['cFile'][i] = outFile
    os.chdir("..")


def checkFileExistence(params):
    os.chdir("DATA")
    for i in range(len(params['mdate'])):
        if not os.path.isfile(params['pFile'][i]):
            logging.error("ERROR: Unable to find phase file {}".format(params['pFile'][i]))
            exit(1)
        if not os.path.isfile(params['cFile'][i]):
            logging.error("ERROR: Unable to find coherence file {}".format(params['cFile'][i]))
            exit(1)
    os.chdir("..")

    
def prepareCustomFiles(params,path):
    root = os.getcwd()
    createCleanDir("DATA")
    os.chdir("DATA")
    for i in range(len(params['mdate'])):
        if path is None:
           myfile = os.path.join(root,params['pFile'][i])
        else:
           myfile = os.path.join(path,params['pFile'][i])
        os.symlink(myfile,params['pFile'][i])

        if path is None:
           myfile = os.path.join(root,params['cFile'][i])
        else:
           myfile = os.path.join(path,params['cFile'][i])
        os.symlink(myfile,params['cFile'][i])
    os.chdir("..")


def createIfgList(params):
    f = open('ifg.list','w')
    for i in range(len(params['mdate'])):
        mdate = params['mdate'][i][0:8]
        sdate = params['sdate'][i][0:8]
        baseline = params['basel'][i]
        f.write ("%s    %s    %s    S1A\n" % (mdate,sdate,baseline))         
    f.close() 


def createExampleRSC(params):
    os.chdir("DATA")
    width,length,trans,proj = saa.read_gdal_file_geo(saa.open_gdal_file(params['pFile'][0]))
    params['width'] = width
    params['length'] = length
    os.chdir("..")
    utctime = params['utctime']
    heading = params['heading']     

    f = open('example.rsc','w')
    f.write("WIDTH             %s\n" % width)
    f.write("FILE_LENGTH       %s\n" % length)
    f.write("WAVELENGTH        0.05546576\n")
    f.write("HEADING_DEG       %s\n" % heading)
    f.write("CENTER_LINE_UTC   %s\n" % utctime)
    f.close()


def fixPrepDataXml(params,templateDir):
    template = '%s/prepdataxml_template.py' % templateDir
    f = open('prepdataxml.py','w')
    g = open(template)
    for line in g.readlines():
        if 'rxlim' in line:
            if params['rxy'] is not None:
                rxlim = params['rxy'][0]
                rylim = params['rxy'][1]
                out = '                       '
                f.write(out)
                out = 'rxlim=[%s,%s], rylim=[%s,%s],\n' % (rxlim-5,rxlim+5,rylim-5,rylim+5)
                f.write(out)
        elif 'xlim' in line:
            out = '                       '
            f.write(out)
            out = 'xlim=[0,%s], ylim=[0,%s],\n' % (params['width'],params['length'])
            f.write(out)
        else:
            f.write(line)
    g.close()
    f.close()


def fixUserfnPy(params,templateDir):
    template = '%s/userfn_template.py' % templateDir
    f = open('userfn.py','w')
    g = open(template)
    for line in g.readlines():
        if 'dirname = ' in line:
            cwd = os.getcwd()
            out = "    dirname = '%s'\n" % cwd
            f.write(out)
        elif 'iname = ' in line:
            out = "    tname = 'LINKS/%s_%s_unw_phase.raw' % (dates1,dates2)\n"
            f.write(out)
            out = "    iname = os.path.join(dirname,tname)\n"
            f.write(out)
        elif 'cname = ' in line:
            out = "    tname = 'LINKS/%s_%s_corr.raw' % (dates1,dates2)\n"
            f.write(out)
            out = "    cname = os.path.join(dirname,tname)\n"
            f.write(out)
        else:
            f.write(line)
    g.close()
    f.close()

      
def makeLinks(params):
    logging.info("Creating new LINKS directory")
    createCleanDir("LINKS")
    os.chdir("LINKS")
    root = "../DATA"
    for i in range(len(params['mdate'])):
        outName = "{}_{}_unw_phase.raw".format(params['mdate'][i][0:8],params['sdate'][i][0:8])
        logging.debug("Linking in file {} to {}".format(os.path.join(root,params['pFile'][i]),outName))
        if not os.path.exists(outName):
            os.symlink(os.path.join(root,params['pFile'][i]),outName)
        else:
            logging.error("ERROR: You have two different interferograms with the same dates")
            logging.error("ERROR: Only one inteferogram per date pair is allowed")
            logging.error("ERROR: Try using the --group switch to process your files as groups")
            exit(1)       
        outName = "{}_{}_corr.raw".format(params['mdate'][i][0:8],params['sdate'][i][0:8])
        logging.debug("Linking in file {} to {}".format(os.path.join(root,params['cFile'][i]),outName))
        os.symlink(os.path.join(root,params['cFile'][i]),outName)
    os.chdir("..")


def fixPrepBasXml(params,templateDir):
    template = '%s/prepbasxml_template.py' % templateDir
    f = open('prepbasxml.py','w')
    g = open(template)
    for line in g.readlines():
        if 'nvalid' in line:
            out ="    g.prepare_sbas_xml(nvalid = %s, netramp=False, atmos='',\n" % int(params['nvalid']*float(len(params['mdate'])))
            f.write(out)
        elif 'filt' in line:
            out ="                        filt = %s)\n" % params['filt']
            f.write(out)
        else:
            f.write(line)
    g.close()
    f.close()

def toRaw(myfile):
    rawname = myfile
    if "wgs84" in rawname:
        rawname = rawname.replace("_wgs84","")
    if "resize" in rawname:
        rawname = rawname.replace("_resize","")
    if "clip" in rawname:
        rawname = rawname.replace("_clip","")
    rawname = rawname.replace(".tif",".raw")
    logging.info("    processing file {} to create file {}".format(myfile,rawname))
    gdal.Translate(rawname,myfile,format="ENVI")
    return rawname

def makeGeotiffFiles(h5File,dataName,params):

    # Open up the HDF5 file
    source = h5py.File("%s" % h5File)
    imgarray = source["%s" % dataName][()]
    maxband = imgarray.shape[0]
    logging.info("Found %s bands to process" % maxband)
 
    # Read a reference file for geolocation and size information
    os.chdir("../DATA")    
    x,y,trans,proj = saa.read_gdal_file_geo(saa.open_gdal_file(params['pFile'][0]))
    os.chdir("../Stack")
    
    # Get the entire date range
    longList = np.unique(params['mdate']+params['sdate'])
    dateList = []
    for i in range(len(longList)):
         dateList.append(longList[i][0:8])
    dateList = np.unique(dateList)
    dateList.sort()
    logging.debug("Datelist is {}".format(dateList))
    
    for cnt in range(maxband):
        logging.info("Processing band %s" % str(cnt + 1))
        if dataName == 'recons':
            if params['train']:
                outFile = "{}_trn_gnt_phase.raw".format(dateList[cnt])
            else:
                outFile = "{}_gnt_phase.raw".format(dateList[cnt])
        elif dataName == 'rawts': 
            if params['train']:
                outFile = "{}_trn_raw_phase.raw".format(dateList[cnt])
            else: 
                outFile = "{}_raw_phase.raw".format(dateList[cnt])
        elif dataName == 'error': 
            if params['train']:
                outFile = "{}_trn_error_phase.raw".format(dateList[cnt])
            else: 
                outFile = "{}_error_phase.raw".format(dateList[cnt])

	cmd = 'gdal_translate -b {} -of ENVI HDF5:"{}"://{} {}'.format(cnt+1,h5File,dataName,outFile)
	execute(cmd,uselogging=True)
      	newdata = np.fromfile(outFile,dtype=np.float32,count=-1)
        img = np.reshape(newdata,(y,x))
        outFile = outFile.replace('.raw','.tif')
        saa.write_gdal_file_float(outFile,trans,proj,img)
        
def makeParmsAPS(params,root):
    f = open("parms_aps.txt","w")
    f.write("UTC_sat: {}\n".format(params['utctime']))
    f.write("merra2_datapath: {}\n".format(os.path.join(root,"merra")))
    f.write("DEM_origin: asf\n")
    f.write("DEM_file: new_dem.tif\n")
    f.write("lambda: 0.05546576\n")
    f.write("incidence_angle: 0.67195\n")
    f.write("date_origin: asf\n")
    f.close       

def prepareFilesForTrain(params):
    for i in range(len(params['pFile'])):
        myfile = params['pFile'][i]
        newfile = "{}_{}_unw_phase.tif".format(params['mdate'][i],params['sdate'][i])
        shutil.copy("{}".format(os.path.join(os.pardir,myfile)),newfile)

def fixFileNamesTrain(params):
    for i in range(len(params['pFile'])):
        newfile = "{}/{}_{}_unw_phase_corrected.tif".format("TRAIN",params['mdate'][i][0:8],params['sdate'][i][0:8])
        if os.path.isfile(newfile):
            params['pFile'][i] = newfile
        else:
            logging.warning("***********************************************************************************")
            logging.warning("WARNING: can't find train output file {} - using uncorrected phase".format(newfile))
            logging.warning("***********************************************************************************")

def procS1StackGIANT(type,output,descFile=None,rxy=None,nvalid=0.8,nsbas=False,filt=0.1,
                     path=None,utcTime=None,heading=None,leave=False,train=False,hyp=None,
                     rawFlag=False,mm=None,errorFlag=False):

    logging.info("***********************************************************************************")
    logging.info("                 STARTING RUN {}".format(output))
    logging.info("***********************************************************************************")
    logging.info("Type of run is {}".format(type))

    if path is not None:
        if path[0] != "/" and os.path.isdir(path):
            root = os.getcwd()
            path = os.path.join(root,path)    
        else:
            logging.error("ERROR: path {} is not a directory!")
            exit(1)
        logging.info("Data path is {}".format(path))

    templateDir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "etc")) 
    logging.debug("Looking for templates in %s" % templateDir)

    if type == 'hyp':
        descFile,hypDir = prepareHypFiles(path,hyp)
    elif type == 'custom':
        if train:
            logging.warning("***********************************************************************************")
            logging.warning("WARNING: Unable to run TRAIN model on custom inputs")
            logging.warning("WARNING: Switching off TRAIN corrections")
            logging.warning("***********************************************************************************")
            train = False
        if descFile is None:
            logging.error("ERROR: Must specify a descriptor file when using custom option")
            exit(1)
        if utcTime is None:
            logging.error("ERROR: Must specify a UTC time when using custom option")
            exit(1)
        if heading is None:
            logging.error("ERROR: Must specify a heading when using custom option")
            exit(1)
    else:
        logging.error("ERROR: Unknown processing type {}".format(type))
        exit(1)
    
    if not os.path.isfile(descFile):   
        logging.error("ERROR: Unable to find descriptor file {}".format(descFile))
        exit(1)

    params = getFileList(descFile) 
    params['type'] = type
    params['rxy'] = rxy
    params['nvalid'] = float(nvalid)
    params['train'] = train
    params['filt'] = filt

    if utcTime is None:
        os.chdir(hypDir)
        txtFile = glob.glob("*/*20*_20*.txt")[0]
        utcTime = getParameter(txtFile,"UTCtime")
        os.chdir("..")
    params['utctime'] = utcTime

    if heading is None:
        os.chdir(hypDir)
        txtFile = glob.glob("*/*20*_20*.txt")[0]
        heading = getParameter(txtFile,"Heading")
        os.chdir("..")
    params['heading'] = heading

    logging.info("Examining list of files to process...")
    for i in range(len(params['mdate'])):
        logging.debug("    found: {} {} {} {}".format(params['mdate'][i],params['sdate'][i],params['pFile'][i],params['cFile'][i]))

    if type == 'custom':
        prepareCustomFiles(params,path)

    checkFileExistence(params) 
    root = os.getcwd()

    logging.info("Reprojecting files...")
    reprojectFiles(params)

    logging.info("Cutting files...")
    os.chdir("DATA")
    cutFiles(params['pFile'])
    cutFiles(params['cFile'])

    for i in range(len(params['mdate'])):
        params['pFile'][i] = params['pFile'][i].replace(".tif","_clip.tif")
        params['cFile'][i] = params['cFile'][i].replace(".tif","_clip.tif")

    logging.info("Resizing files...")
    resizeFiles(params)

    if train:
        logging.info("***********************************************************************************")
        logging.info("          PREPARING TO RUN THE TRAIN MERRA2 WEATHER MODEL")
        logging.info("***********************************************************************************")
        createCleanDir("TRAIN")
        os.chdir("TRAIN")
        makeParmsAPS(params,root)
        prepareFilesForTrain(params)
        myfile = os.path.join(os.pardir,params['pFile'][0])
        aps_weather_model("merra2",1,4,myfile)
        os.chdir("..")
        fixFileNamesTrain(params) 
 
    logging.info("Translating files to raw format...")
    for i in range(len(params['pFile'])):
        params['pFile'][i] = toRaw(params['pFile'][i])
        params['cFile'][i] = toRaw(params['cFile'][i])
        
    if not leave:
        for myfile in glob.glob("*_wgs84.tif"):
            os.remove(myfile)
        for myfile in glob.glob("*_clip.tif"):
            os.remove(myfile)
        for myfile in glob.glob("*_resize.tif"):
            os.remove(myfile)
    os.chdir("..")
 
    createIfgList(params)
    createExampleRSC(params)
    fixPrepDataXml(params,templateDir)
    fixUserfnPy(params,templateDir)
    makeLinks(params)
    fixPrepBasXml(params,templateDir)

    execute("python prepdataxml.py",uselogging=True)
    execute("PrepIgramStack.py",uselogging=True)
    execute("python prepbasxml.py",uselogging=True)

    if nsbas == False:
        logging.info("Running SBAS inversion")
        if errorFlag:
            execute("SBASxval.py",uselogging=True)
            h5File = "LS-xval.h5"
        else:
            execute("SBASInvert.py",uselogging=True)
            h5File = "LS-PARAMS.h5"
    else:
        logging.info("Running NSBAS inversion")
        if errorFlag:
            h5File = "NSBAS-xval.h5"
            execute("NSBASxval.py -o {}".format(h5file),uselogging=True)
        else:
            execute("NSBASInvert.py",uselogging=True)
            h5File = "NSBAS-PARAMS.h5"
    
    os.chdir("Stack")
    filelist =  makePNG.mkMovie(h5File,"recons",mm=mm)
    filelist.sort()

    if rawFlag:
        filelist2 = makePNG.mkMovie(h5File,"rawts",mm=mm)
        filelist2.sort()
    elif errorFlag:
        filelist2 = makePNG.mkMovie(h5File,"error",mm=mm)
        filelist2.sort()
    
    # Get the entire date range
    longList = np.unique(params['mdate']+params['sdate'])
    dateList = []
    for i in range(len(longList)):
         dateList.append(longList[i][0:8])
    dateList = np.unique(dateList)
    dateList.sort()

    # Add annotations to files 
    cnt = 0
    for myfile in filelist:
        execute("convert {FILE} -gravity north  -annotate +0+5 '{DATE}' anno_{FILE}".format(FILE=myfile,DATE=dateList[cnt]),uselogging=True)
        cnt = cnt + 1
    if train:
        name = "{}_train.gif".format(output)
    else:
        name = "{}.gif".format(output)
    # Make the animation
    execute("convert -delay 120 -loop 0 anno_*.png {}".format(name),uselogging=True)

    if rawFlag:
        for myfile in glob.glob("anno_*.png"):
            os.remove(myfile)
        cnt = 0
        for myfile in filelist2:
           execute("convert {FILE} -gravity north  -annotate +0+5 '{DATE}' anno_{FILE}".format(FILE=myfile,DATE=dateList[cnt]),uselogging=True)
           cnt = cnt + 1
        rawname = name.replace(".gif","_rawts.gif")
        # Make the animation
        execute("convert -delay 120 -loop 0 anno_*.png {}".format(rawname),uselogging=True)
    elif errorFlag:
        for myfile in glob.glob("anno_*.png"):
            os.remove(myfile)
        cnt = 0
        for myfile in filelist2:
           execute("convert {FILE} -gravity north  -annotate +0+5 '{DATE}' anno_{FILE}".format(FILE=myfile,DATE=dateList[cnt]),uselogging=True)
           cnt = cnt + 1
        rawname = name.replace(".gif","_error.gif")
        # Make the animation
        execute("convert -delay 120 -loop 0 anno_*.png {}".format(rawname),uselogging=True)

    # Get product directory ready
    os.chdir("..")
    prodDir = "PRODUCT_{}".format(output)
    createCleanDir(prodDir)

    os.chdir("Stack")    

    shutil.move(name,"../{}".format(prodDir))
    if rawFlag or errorFlag:
        shutil.move(rawname,"../{}".format(prodDir))
        
    makeGeotiffFiles(h5File,"recons",params)
    if rawFlag:
       makeGeotiffFiles(h5File,"rawts",params)
    elif errorFlag:
       makeGeotiffFiles(h5File,"error",params)

    # Move files from Stack directory
    for myfile in glob.glob("*.tif"):
        shutil.move(myfile,"../{}".format(prodDir))
    shutil.move(h5File,"../{}/{}.h5".format(prodDir,output))
    os.chdir("..")

    # Move files from main directory 
#    os.mkdir("{}/GIAnT_FILES".format(prodDir))
#    shutil.move("prepdataxml.py","{}/GIAnT_FILES".format(prodDir))
#    shutil.move("prepbasxml.py","{}/GIAnT_FILES".format(prodDir))
#    shutil.move("userfn.py","{}/GIAnT_FILES".format(prodDir))
#    shutil.move("ifg.list","{}/GIAnT_FILES".format(prodDir))
#    shutil.move("example.rsc","{}/GIAnT_FILES".format(prodDir))
    shutil.copy(descFile,prodDir)

    if not leave:
        if type == 'hyp':
            shutil.rmtree(hypDir)
        shutil.rmtree("DATA")
        shutil.rmtree("LINKS")
        shutil.rmtree("Stack")
        shutil.rmtree("Figs")

        os.remove("data.xml")
        os.remove("userfn.pyc")
        os.remove("sbas.xml")
	os.remove("prepdataxml.py")
	os.remove("prepbasxml.py")
	os.remove("userfn.py")
	os.remove("ifg.list")
	os.remove("example.rsc")
       
        if train:
            for myfile in glob.glob("merra/*/*.xyz"):
                 os.remove(myfile)
   
    logging.info("***********************************************************************************")
    logging.info("                 END OF RUN {}".format(output))
    logging.info("***********************************************************************************")


def printParameters(type,output,descFile=None,rxy=None,nvalid=0.8,nsbas=False,filt=0.1,
                path=None,utcTime=None,heading=None,leave=False,train=False,hyp=None,
                zipFlag=False,group=False,rawFlag=False,mm=None,errorFlag=False,api_key=None):

    cmd = "procS1StackGIANT.py "
    
    if descFile:
        cmd = cmd + "--descFile {} ".format(descFile)
    if rxy:
        cmd = cmd + "--rxy {} ".format(rxy)
    if nvalid != 0.80:
        cmd = cmd + "--nvalid {} ".format(nvalid)
    if nsbas:
        cmd = cmd + "--nsbas "
    if filt != 0.1:
        cmd = cmd + "--filter {} ".format(filt)
    if path:
        cmd = cmd + "--path {} ".format(path)
    if utcTime:
        cmd = cmd + "--utc {} ".format(utc)
    if heading:
        cmd = cmd + "--heading {} ".format(heading)
    if leave:
       cmd = cmd + "--leave "
    if train:
       cmd = cmd + "--train "
    if hyp:
       cmd = cmd + '--input "{}" '.format(hyp)
    if zipFlag: 
       cmd = cmd + "--zip "
    if group: 
       cmd = cmd + "--group "
    if rawFlag:
       cmd = cmd + "--raw "
    if mm:
       cmd = cmd + "--minmax {} {} ".format(mm[0],mm[1])
    if errorFlag:
       cmd = cmd + "--error "
    if api_key:
       cmd = cmd + "--apikey {} ".format(api_key)

    cmd = cmd + "{} ".format(type)
    cmd = cmd + "{} ".format(output)

    logging.info("Command Run: {}".format(cmd))
    logging.info("Parameters for this run:")
    logging.info("    type of run              : {}".format(type))
    logging.info("    output name              : {}".format(output))
    logging.info("    descriptor file          : {}".format(descFile))
    logging.info("    region x y               : {}".format(rxy))
    logging.info("    nvalid                   : {}".format(nvalid))
    logging.info("    nsbas flag               : {}".format(nsbas))
    logging.info("    filter flag              : {}".format(filt))
    logging.info("    path to input files      : {}".format(path))
    logging.info("    utc time                 : {}".format(utcTime))
    logging.info("    heading                  : {}".format(heading))
    logging.info("    leave intermediates      : {}".format(leave))
    logging.info("    train flag               : {}".format(train))
    logging.info("    hyp name of subscription : {}".format(hyp))
    logging.info("    zip flag                 : {}".format(zipFlag))
    logging.info("    group flag               : {}".format(group))
    logging.info("    raw time series flag     : {}".format(rawFlag))
    logging.info("    min/max scale range      : {}".format(mm))
    logging.info("    error estimation         : {}".format(errorFlag))
    logging.info("    name of api-key file     : {}".format(api_key))
    logging.info("\n")

def procS1StackGroupsGIANT (type,output,descFile=None,rxy=None,nvalid=0.8,nsbas=False,filt=0.1,
                     path=None,utcTime=None,heading=None,leave=False,train=False,hyp=None,
                     zipFlag=False,group=False,rawFlag=False,mm=None,errorFlag=False,api_key=None):

    logging.info("***********************************************************************************")
    logging.info("                 STARTING RUN {}".format(output))
    logging.info("***********************************************************************************")

    printParameters(type,output,descFile=descFile,rxy=rxy,nvalid=nvalid,nsbas=nsbas,filt=filt,
                path=path,utcTime=utcTime,heading=heading,leave=leave,train=train,hyp=hyp,
                zipFlag=zipFlag,group=group,rawFlag=rawFlag,mm=mm,errorFlag=errorFlag,
                api_key=api_key)

    if hyp:
        logging.info("Using Hyp3 subscription named {} to download input files".format(hyp))
        if api_key is not None:
            config = configparser.ConfigParser()
            config.read(api_key)
            s = 'hyp3-API-credentials'
            api = API(config.get(s, 'username'), api_key=config.get(s, 'api_key'))
        
        else:
            username,password = getUsernamePassword()
            api = API(username)
            api.login(password=password)
        download_products(api,sub_name=hyp)
        zipFlag = True
        path = "hyp3-products"

    if zipFlag:
        unzipFiles(path,"hyp3-products-unzipped")
        zipFlag = False
        path = "hyp3-products-unzipped"

    if type == 'hyp' and group:
        # Make path into an absolute path
        if path is not None:
            if path[0] != "/" and os.path.isdir(path):
                root = os.getcwd()
                path = os.path.join(root,path)    
            else:
                logging.error("ERROR: path {} is not a directory!")
                exit(1)
            logging.info("Data path is {}".format(path))
        else:
            path = os.getcwd()
 
        filelist = []
        for myfile in os.listdir(path):
            if os.path.isdir(os.path.join(path,myfile)):
                filelist.append(myfile)

        if len(filelist)==0:
            logging.error("ERROR: Unable to find files to process")
            exit(1)

        classes, filelists = sortByTime(path,filelist,"insar")
        for i in range(len(classes)):
            if len(filelists[i])>2:
                mydir = "DATA_{}".format(classes[i])
                createCleanDir(mydir)
                for myfile in filelists[i]:
                    thisDir = "../sorted_{}".format(classes[i])
                    inFile = "{}/{}".format(thisDir,os.path.basename(myfile))
                    outFile = "{}/{}".format(mydir,os.path.basename(myfile))
                    logging.debug("Linking file {} to {}".format(inFile,outFile))
                    os.symlink(inFile,outFile)
                outfile = output + "_" + classes[i]
                procS1StackGIANT(type,outfile,descFile=descFile,rxy=rxy,nvalid=nvalid,
                     nsbas=nsbas,filt=filt, path=mydir,utcTime=utcTime,heading=heading,
                     leave=leave,train=train,hyp=hyp,rawFlag=rawFlag,mm=mm,errorFlag=errorFlag)
                shutil.rmtree(mydir)
    else:
        procS1StackGIANT(type,output,descFile=descFile,rxy=rxy,nvalid=nvalid,nsbas=nsbas,
             filt=filt,path=path,utcTime=utcTime,heading=heading,leave=leave,train=train,
             hyp=hyp,rawFlag=rawFlag,mm=mm,errorFlag=errorFlag)

    if not leave:
        if group:
            for myfile in glob.glob("sorted_*"):
                shutil.rmtree(myfile)

    logging.info("***********************************************************************************")
    logging.info("                 END OF RUN {}".format(output))
    logging.info("***********************************************************************************")

if __name__ == '__main__':

  parser = argparse.ArgumentParser(prog='procS1StackGIANT.py',description='Run a stack of interferograms through GIANT')
  parser.add_argument("type",choices=['hyp','custom'],help='Type of input files')
  parser.add_argument("output",help='Basename to be used for output files')
  parser.add_argument("-a","--apikey",help='Use api-key found in given file to login. Default is to login with netrc credentials')
  parser.add_argument("-d","--desc",help='Name of descriptor file')
  parser.add_argument("-f","--filter",type=float,default=0.1,help='Filter length in years (Default=0.1)')
  parser.add_argument("-g","--group",action="store_true",help="Group files by time before processing")
  parser.add_argument("-i","--input",help="Name of the Hyp3 subscription to download for input files")
  parser.add_argument("-l","--leave",action="store_true",help="Leave intermediate files in place")
  parser.add_argument("-m","--minmax",type=float,nargs=2,help='Minium and maximum scale for animations',metavar=('MIN', 'MAX'))
  parser.add_argument("-n","--nsbas",action="store_true",help='Run NSBAS inversion instead of SBAS')
  parser.add_argument("-p","--path",help='Path to input files')
  parser.add_argument("-r","--rxy",type=float,nargs=2,help='Set the point to use as zero; Default is chosen by ISCE',metavar=('X', 'Y'))
  parser.add_argument("-s","--heading",type=float,help='Spacecraft heading at time of acquisitions')
  parser.add_argument("-t","--train",action="store_true",help="Run TRAIN weather model correction prior to time series inversion")
  parser.add_argument("-u","--utc",type=float,help='UTC time of image stack')
  parser.add_argument("-v","--nvalid",type=float,default=0.8,
      help='Fraction of samples that must be valid for a point to be included for NSBAS inversion.  (Default=0.8)')
  parser.add_argument("-z","--zip",action='store_true',help="Start from hyp3 zip files instead of directories")

  group = parser.add_mutually_exclusive_group()
  group.add_argument("-e","--error",action="store_true",help="Create animation and geotiffs of error estimates")
  group.add_argument("-w","--raw",action="store_true",help='Create animation and geotiffs of raw time series')

  args = parser.parse_args()

  logFile = "{}_log.txt".format(args.output)
  logging.basicConfig(filename=logFile,format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',level=logging.DEBUG)
  logging.getLogger().addHandler(logging.StreamHandler())

  procS1StackGroupsGIANT(args.type,args.output,descFile=args.desc,rxy=args.rxy,nvalid=args.nvalid,nsbas=args.nsbas,
                   filt=args.filter,path=args.path,utcTime=args.utc,heading=args.heading,leave=args.leave,
                   train=args.train,hyp=args.input,zipFlag=args.zip,group=args.group,rawFlag=args.raw,mm=args.minmax,
                   errorFlag=args.error,api_key=args.apikey)

