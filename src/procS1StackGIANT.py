#!/usr/bin/env python
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
###############################################################################
# rtc_sentinel.py
#
# Project:  APD HYP3
# Purpose:  Create INSAR time series outputs from GIAnT 
#  
# Author:   Tom Logan
#
# Issues/Caveats:
#
###############################################################################
# Copyright (c) 2017, Alaska Satellite Facility
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

def prepareHypFiles(path):

    createCleanDir("HYP")
    if path is None:
        for myfile in os.listdir("."):
            if ".zip" in myfile:
                print "    unzipping file {}".format(myfile)
                zip_ref = zipfile.ZipFile(myfile, 'r')
                zip_ref.extractall("HYP")
                zip_ref.close()
    else:
        for myfile in os.listdir(path):
            if ".zip" in myfile:
                print "    unzipping file {}".format(myfile)
                zip_ref = zipfile.ZipFile(os.path.join(path,myfile), 'r')
                zip_ref.extractall("HYP")
                zip_ref.close()

    os.chdir("HYP")

    unw_cnt = len(glob.glob("*/*_unw_phase.tif"))
    cor_cnt = len(glob.glob("*/*_corr.tif"))
    if unw_cnt != cor_cnt:
        print "You are missing files!!! unw_cnt = %s; cor_cnt = %s" % (unw_cnt,cor_cnt)
        exit(1)

    f = open('../igram_list.txt','w')
    for myfile in glob.glob("*/*_unw_phase.tif"):
        mdate = os.path.basename(myfile.split("_")[0])
        sdate = myfile.split("_")[1]
        pFile = os.path.basename(myfile)
        cFile = os.path.basename(myfile.replace("_unw_phase.tif","_corr.tif"))
        txtFile = glob.glob("{}/20*_20*.txt".format(os.path.dirname(myfile)))[0]
        baseline = getParameter(txtFile,"Baseline")
        f.write("{} {} {} {} {}\n".format(mdate,sdate,pFile,cFile,baseline))
    f.close()

    os.chdir("..")
    createCleanDir("DATA")
    os.chdir("DATA")
    for myfile in glob.glob("../HYP/*/*_unw_phase.tif"):
         os.symlink(myfile,os.path.basename(myfile))
    for myfile in glob.glob("../HYP/*/*_corr.tif"):
         os.symlink(myfile,os.path.basename(myfile))
    os.chdir("..") 

    return('igram_list.txt') 


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


def reprojectFiles(params):
    os.chdir("DATA") 
    for i in range(len(params['mdate'])):
        x,y,trans,proj = saa.read_gdal_file_geo(saa.open_gdal_file(params['pFile'][i]))
        if "PROJCS" in proj:
            outFile = params['pFile'][i].replace(".tif","_wgs84.tif")
            print "    processing file {} to create file {}".format(params['pFile'][i],outFile)
            gdal.Warp(outFile,params['pFile'][i],dstSRS="EPSG:4326")
            params['pFile'][i] = outFile
            outFile = params['cFile'][i].replace(".tif","_wgs84.tif")
            print "    processing file {} to create file {}".format(params['cFile'][i],outFile)
            gdal.Warp(outFile,params['cFile'][i],dstSRS="EPSG:4326")
            params['cFile'][i] = outFile
    os.chdir("..")


def checkFileExistence(params):
    os.chdir("DATA")
    for i in range(len(params['mdate'])):
        if not os.path.isfile(params['pFile'][i]):
            print "ERROR: Unable to find phase file {}".format(params['pFile'][i])
            exit(1)
        if not os.path.isfile(params['cFile'][i]):
            print "ERROR: Unable to find coherence file {}".format(params['cFile'][i])
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
                print params['rxy']
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
    createCleanDir("LINKS")
    print "Creating new LINKS directory"
    os.chdir("LINKS")
    root = "../DATA"
    for i in range(len(params['mdate'])):
        outName = "{}_{}_unw_phase.raw".format(params['mdate'][i][0:8],params['sdate'][i][0:8])
        os.symlink(os.path.join(root,params['pFile'][i]),outName)
        outName = "{}_{}_corr.raw".format(params['mdate'][i][0:8],params['sdate'][i][0:8])
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
    if "wgs84" in myfile:
        rawname = myfile.replace("_wgs84_clip.tif",".raw")
    else:
        rawname = myfile.replace("_clip.tif",".raw")
    print "    processing file {} to create file {}".format(myfile,rawname)
    gdal.Translate(rawname,myfile,format="ENVI")
    return rawname


def makeGeotiffFiles(h5File,params):

    # Open up the HDF5 file
    os.chdir("Stack")
    source = h5py.File("%s" % h5File)
    imgarray = source["recons"][()]
    maxband = imgarray.shape[0]
    print "Found %s bands to process" % maxband
 
    # Read a reference file for geolocation and size information
    os.chdir("../DATA")    
    x,y,trans,proj = saa.read_gdal_file_geo(saa.open_gdal_file(params['pFile'][0]))
    os.chdir("../Stack")
    
    # Get the entire date range
    dateList = np.unique(params['mdate']+params['sdate'])
    dateList.sort()
    print "Datelist is {}".format(dateList)
    
    for cnt in range(maxband):
        print "Processing band %s" % str(cnt + 1)
        outFile = "{}_phase.raw".format(dateList[cnt])
	cmd = 'gdal_translate -b {} -of ENVI HDF5:"{}"://recons {}'.format(cnt+1,h5File,outFile)
	execute(cmd)
      	newdata = np.fromfile(outFile,dtype=np.float32,count=-1)
        img = np.reshape(newdata,(y,x))
        outFile = outFile.replace('.raw','.tif')
        saa.write_gdal_file_float(outFile,trans,proj,img)
        
    for myfile in glob.glob("*.tif"):
        shutil.move(myfile,"../PRODUCT")
    os.chdir("..")
         
def createCleanDir(dirName):
    if not os.path.isdir(dirName):
        os.mkdir(dirName)
    else:
        print "Cleaning up old {} directory".format(dirName)
        shutil.rmtree(dirName) 
        os.mkdir(dirName)

def makeParmsAPS(params):
    root = os.getcwd()
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
        newfile = "{}/{}_{}_unw_phase_corrected.tif".format("TRAIN",params['mdate'][i],params['sdate'][i])
        if os.path.isfile(newfile):
            params['pFile'][i] = newfile
        else:
            print "***********************************************************************************"
            print "***********************************************************************************"
            print "WARNING: can't find train output file {} - using uncorrected phase".format(newfile)
            print "***********************************************************************************"
            print "***********************************************************************************"

def procS1StackGIANT(type,output,descFile=None,rxy=None,nvalid=0.8,nsbas=False,filt=0.1,
                     path=None,utcTime=None,heading=None,leave=False,train=False):

    print "Type of run is {}".format(type)

    if path is not None:
        if "/" not in path and os.path.isdir(path):
            root = os.getcwd()
            path = os.path.join(root,path)    
        print "Data path is {}".format(path)

    templateDir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "etc")) 
    print "Looking for templates in %s" % templateDir

    if type == 'hyp':
        descFile = prepareHypFiles(path)
    elif type == 'custom':
        if train:
            print "***********************************************************************************"
            print "***********************************************************************************"
            print "WARNING: Unable to run TRAIN model on custom inputs"
            print "WARNING: Switching off TRAIN corrections"
            print "***********************************************************************************"
            print "***********************************************************************************"
            train = False
        if descFile is None:
            print "ERROR: Must specify a descriptor file when using custom option"
            exit(1)
        if utcTime is None:
            print "ERROR: Must specify a UTC time when using custom option"
            exit(1)
        if heading is None:
            print "ERROR: Must specify a heading when using custom option"
            exit(1)
    else:
        print "ERROR: Unknown processing type {}".format(type)
        exit(1)
    
    if not os.path.isfile(descFile):   
        print "ERROR: Unable to find descriptor file {}".format(descFile)
        exit(1)

    params = getFileList(descFile) 
    params['type'] = type
    params['rxy'] = rxy
    params['nvalid'] = float(nvalid)
    params['filt'] = filt

    if utcTime is None:
        os.chdir("HYP")
        txtFile = glob.glob("*/20*_20*.txt")[0]
        utcTime = getParameter(txtFile,"UTCtime")
        os.chdir("..")
    params['utctime'] = utcTime

    if heading is None:
        os.chdir("HYP")
        txtFile = glob.glob("*/20*_20*.txt")[0]
        heading = getParameter(txtFile,"Heading")
        os.chdir("..")
    params['heading'] = heading

    print "Examining list of files to process..."
    for i in range(len(params['mdate'])):
        print "    found: {} {} {} {}".format(params['mdate'][i],params['sdate'][i],params['pFile'][i],params['cFile'][i])

    if type == 'custom':
        prepareCustomFiles(params,path)

    checkFileExistence(params) 

    print "Reprojecting files..."
    reprojectFiles(params)

    print "Cutting files..."
    os.chdir("DATA")
    cutFiles(params['pFile'])
    cutFiles(params['cFile'])

    for i in range(len(params['mdate'])):
        params['pFile'][i] = params['pFile'][i].replace(".tif","_clip.tif")
        params['cFile'][i] = params['cFile'][i].replace(".tif","_clip.tif")

    if train:
        createCleanDir("TRAIN")
        os.chdir("TRAIN")
        makeParmsAPS(params)
        prepareFilesForTrain(params)
        myfile = os.path.join(os.pardir,params['pFile'][0])
        aps_weather_model("merra2",0,4,myfile)
        os.chdir("..")
        fixFileNamesTrain(params) 
 
    print "Translating files to raw format..."
    for i in range(len(params['pFile'])):
        params['pFile'][i] = toRaw(params['pFile'][i])
        params['cFile'][i] = toRaw(params['cFile'][i])
        
    if not leave:
        for myfile in glob.glob("*_wgs84.tif"):
            os.remove(myfile)
        for myfile in glob.glob("*_clip.tif"):
            os.remove(myfile)
    os.chdir("..")
 
    createIfgList(params)
    createExampleRSC(params)
    fixPrepDataXml(params,templateDir)
    fixUserfnPy(params,templateDir)
    makeLinks(params)
    fixPrepBasXml(params,templateDir)

    execute("python prepdataxml.py")
    execute("PrepIgramStack.py")
    execute("python prepbasxml.py")

    if nsbas == False:
        print "Running SBAS inversion"
        execute("SBASInvert.py")
        print "Use plotts.py -f Stack/LS-PARAMS.h5 -y -30 10 to view results"
        h5File = "LS-PARAMS.h5"
    else:
        print "Running NSBAS inversion"
        execute("NSBASInvert.py")
        print "Use plotts.py -f Stack/NSBAS-PARAMS.h5 -y -30 10 to view results"
        h5File = "NSBAS-PARAMS.h5"
    
    os.chdir("Stack")
    makePNG.mkMovie(h5File)
    
    # Get the entire date range
    dateList = np.unique(params['mdate']+params['sdate'])
    dateList.sort()
    filelist = glob.glob("frame*.png")
    filelist.sort()
 
    name = "{}.gif".format(output)
    cnt = 0
    for myfile in filelist:
        execute("convert {FILE} -gravity north  -annotate +0+5 '{DATE}' anno_{FILE}.png".format(FILE=myfile,DATE=dateList[cnt]))
        cnt = cnt + 1
    execute("convert -delay 120 -loop 0 anno_frame*.png {}".format(name))
    os.chdir("..")
    createCleanDir("PRODUCT")
    os.chdir("Stack")    
    shutil.move(name,"../PRODUCT")
    os.chdir("..")
    makeGeotiffFiles(h5File,params)
    os.chdir("Stack")
    shutil.move(h5File,"../PRODUCT/{}.h5".format(output))
    os.chdir("..")

    # Clean up
    os.mkdir("PRODUCT/GIAnT_FILES")
    shutil.move("prepdataxml.py","PRODUCT/GIAnT_FILES")
    shutil.move("prepbasxml.py","PRODUCT/GIAnT_FILES")
    shutil.move("userfn.py","PRODUCT/GIAnT_FILES")
    shutil.move("ifg.list","PRODUCT/GIAnT_FILES")
    shutil.move("example.rsc","PRODUCT/GIAnT_FILES")
    shutil.copy(descFile,"PRODUCT")

    if not leave:
        if type == "hyp":
            shutil.rmtree("HYP")
        shutil.rmtree("DATA")
        shutil.rmtree("LINKS")
        shutil.rmtree("Stack")
        shutil.rmtree("Figs")
        os.remove("data.xml")
        os.remove("userfn.pyc")
        os.remove("sbas.xml")

if __name__ == '__main__':

  parser = argparse.ArgumentParser(prog='procS1StackGIANT.py',description='Run a stack of interferograms through GIANT')
  parser.add_argument("type",choices=['hyp','custom'],help='Type of input files')
  parser.add_argument("output",help='Basename to be used for output files')
  parser.add_argument("-d","--desc",help='Name of descriptor file')
  parser.add_argument("-f","--filter",type=float,default=0.1,help='Filter length in years (Default=0.1)')
  parser.add_argument("-l","--leave",action="store_true",help="Leave intermediate files in place")
  parser.add_argument("-n","--nsbas",action="store_true",help='Run NSBAS inversion instead of SBAS')
  parser.add_argument("-p","--path",help='Path to input files')
  parser.add_argument("-r","--rxy",type=float,nargs=2,help='Set the point to use as zero; Default is choosen by ISCE')
  parser.add_argument("-s","--heading",type=float,help='Spacecraft heading at time of acquisitions')
  parser.add_argument("-t","--train",action="store_true",help="Run TRAIN weather model correction prior to time series inversion")
  parser.add_argument("-u","--utc",type=float,help='UTC time of image stack')
  parser.add_argument("-v","--nvalid",type=float,default=0.8,help='Fraction of samples that must be valid for a point to be included for NSBAS inversion.  (Default=0.8)')
  args = parser.parse_args()

  procS1StackGIANT(args.type,args.output,descFile=args.desc,rxy=args.rxy,nvalid=args.nvalid,nsbas=args.nsbas,
                   filt=args.filter,path=args.path,utcTime=args.utc,heading=args.heading,leave=args.leave,
                   train=args.train)

