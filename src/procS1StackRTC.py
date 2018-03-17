#!/usr/bin/env python
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
###############################################################################
# rtc_sentinel.py
#
# Project:  APD HYP3
# Purpose:  Create RTC times series from outputs of hyp3
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
import os, re
import argparse
import zipfile
import shutil
import glob
from osgeo import gdal
import ogr
from execute import execute
import saa_func_lib as saa
import numpy as np
from cutGeotiffsByLine import cutGeotiffsByLine
from sortByTime import sortByTime
from download_products import download_products
from getUsernamePassword import getUsernamePassword
from asf_hyp3 import API
from os.path import expanduser
import logging
from time_series_utils import *

def apply_speckle_filter(fi):
    outfile = fi.replace('.tif','_sf.tif')
    (x,y,trans,proj,data) = saa.read_gdal_file(saa.open_gdal_file(fi))
    infile = "tmp.bin"
    f = open(infile,"wb")
    f.write(data)
    f.close()
    
    cmd = "swap_bytes tmp.bin tmp2.bin 4"
    execute(cmd)
     
    cmd = "enh_lee tmp2.bin tmp3.bin %s 1 4 7 7" % x
    execute(cmd)

    cmd = "swap_bytes tmp3.bin tmp4.bin 4"
    execute(cmd)
     
    data = np.fromfile("tmp4.bin",dtype=np.float32)
    data = np.reshape(data,(y,x))
    saa.write_gdal_file_float(outfile,trans,proj,data)
    os.remove("tmp.bin")
    os.remove("tmp2.bin")
    os.remove("tmp3.bin")
    os.remove("tmp4.bin")
    return(outfile)

def create_dB(fi):
    (x,y,trans,proj,data) = saa.read_gdal_file(saa.open_gdal_file(fi))

# If your input data is amplitude data, use these 2 lines:
#    pwrdata = data*data
#    dBdata = 10 * np.log(pwrdata)

# If your input data is power data, use the following line:
    dBdata = 10 * np.log(data)

    outfile = fi.replace('.tif','_dB.tif')
    saa.write_gdal_file_float(outfile,trans,proj,dBdata)
    return(outfile)

def pwr2amp(fi):
    x,y,trans,proj,data = saa.read_gdal_file(saa.open_gdal_file(fi))
    ampdata = np.sqrt(data)
    outfile = fi.replace(".tif","_amp.tif")
    saa.write_gdal_file_float(outfile,trans,proj,ampdata)
    return(outfile)

def amp2pwr(filelist):
    for i in range(len(filelist)):
        x,y,trans,proj,data = saa.read_gdal_file(saa.open_gdal_file(filelist[i]))
        pwrdata = data*data
        outfile = filelist[i].replace(".tif","_amp.tif")
        saa.write_gdal_file_float(outfile,trans,proj,pwrdata)
        filelist[i] = outfile
    return(filelist)

def byteScale(fi,lower,upper):
    outfile = fi.replace('.tif','%s_%s.tif' % (int(lower),int(upper)))
    (x,y,trans,proj,data) = saa.read_gdal_file(saa.open_gdal_file(fi))
    dst = gdal.Translate(outfile,fi,outputType=gdal.GDT_Byte,scaleParams=[[lower,upper]])
    return(outfile)

def get2sigmacutoffs(fi):
    (x,y,trans,proj,data) = saa.read_gdal_file(saa.open_gdal_file(fi))
    top = np.percentile(data,98)
    data[data>top]=top
    stddev = np.std(data)
    mean = np.mean(data)
    lo = mean - 2*stddev
    hi = mean + 2*stddev
    return lo,hi

def changeRes(res,fi):
    outfile = fi.replace('.tif','_%sm.tif' % int(res))
    dst = gdal.Translate(outfile,fi,xRes=res,yRes=res,resampleAlg="average")
    return(outfile)

def cut(pt1,pt2,pt3,pt4,fi,thresh=0.4):
    outfile = fi.replace('.tif','_clipped.tif')
    coords = (pt1,pt2,pt3,pt4)
    dst = gdal.Translate(outfile,fi,projWin=coords)
    x,y,trans,proj,data = saa.read_gdal_file(dst)
    data[data!=0]=1
    frac = np.sum(np.sum(data))/(x*y)
    if frac < thresh: 
        logging.info("    Image fraction ({}) less than threshold of {} discarding".format(frac,thresh))
        os.remove(outfile)
        outfile=None
    return(outfile,frac)

# anno_s1b-iw-rtcm-vv-S1B_IW_GRDH_1SDV_20180118T031947_20180118T032012_009220_01084D_97C9_clipped_dB-40_0.png
#

def getDates(filelist):
    dates = []
    for myfile in filelist:
        myfile = os.path.basename(myfile)
        s = myfile.split("-")[4]
        
        if len(s) <= 26:
            t = s.split("_")[0]
            dates.append(t)
        else:       
            t = s.split("_")[4]
            dates.append(t)
            
    return(dates)

def report_stats(myfile,tmpfile,frac):
    msg = "{} : {} : ".format(myfile,frac)
    if tmpfile is None:
        msg = msg + "discarded"
    else:
        msg = msg + "kept"
    logging.info(msg)


def filterStack(filelist):
    logging.info("Applying speckle filter")
    for i in range(len(filelist)):
        filelist[i] = apply_speckle_filter(filelist[i]) 
    return filelist

def changeResStack(filelist,res):
    logging.info("Changing resolution to {}".format(res))
    for i in range(len(filelist)):
        filelist[i] = changeRes(res,filelist[i]) 
    return filelist


def fix_projections(filelist):

    # Open file1, get projection and pixsize
    (x,y,trans,proj,data) = saa.read_gdal_file(saa.open_gdal_file(filelist[0]))
    pixsize = trans[1]

    # Make sure that UTM projections match
    ptr = proj.find("UTM zone ")
    if ptr != -1:
        (zone1,hemi) = [t(s) for t,s in zip((int,str), re.search("(\d+)(.)",proj[ptr:]).groups())]
        for x in range(len(filelist)-1):
            file2 = filelist[x+1]

            # Open up file2, get projection 
            dst2 = gdal.Open(file2)
            p2 = dst2.GetProjection()

            # Cut the UTM zone out of projection2 
            ptr = p2.find("UTM zone ")
            zone2 = re.search("(\d+)",p2[ptr:]).groups()
            zone2 = int(zone2[0])

            if zone1 != zone2:
                print "Projections don't match... Reprojecting %s" % file2
                if hemi == "N":
                    proj = ('EPSG:326%02d' % int(zone1))
                else:
                    proj = ('EPSG:327%02d' % int(zone1))
                name = file2.replace(".tif","_reproj.tif")
                gdal.Warp(name,file2,dstSRS=proj,xRes=pixsize,yRes=pixsize)
                filelist[x+1] = name
    return(filelist)

def cutStack(filelist,overlap,clip,shape,thresh):
    filelist = fix_projections(filelist)
    if overlap:
        logging.info("Cutting files to common overlap")
        power_filelist = cutGeotiffsByLine(filelist)
    elif clip is not None:
        pt1 = clip[0]
        pt2 = clip[1]
        pt3 = clip[2]
        pt4 = clip[3]
        logging.info("Clipping to bounding box {} {} {} {}".format(pt1,pt2,pt3,pt4))
        logging.info("Statistics for clipping:")
        logging.info("file name : percent overlap : result")
        power_filelist = []
        for i in range(len(filelist)):
            myfile,frac = cut(pt1,pt2,pt3,pt4,filelist[i],thresh=thresh)
            report_stats(filelist[i],myfile,frac)
            if myfile is not None:
                power_filelist.append(myfile)
    elif shape is not None:
        logging.info("Clipping to shape file {}".format(shape))
        power_filelist = []
        for i in range(len(filelist)):
            outGeoTIFF = fi.replace('.tif','_shape.tif')
            subset_geotiff_shape(filelist[i], shape, outGeoTIFF)
            if os.path.isfile(outGeoTIFF):
                power_filelist.append(outGeoTIFF)
    else:
        power_filelist = filelist

    return power_filelist


def findBestFit(filelist,clip):

    print "got file list {}".format(filelist)

    lon_min = clip[0]
    lat_max = clip[1]
    lon_max = clip[2]
    lat_min = clip[3]
    wkt1 = "POLYGON ((%s %s, %s %s, %s %s, %s %s, %s %s))" % (lat_min,lon_min,lat_max,lon_min,lat_max,lon_max,lat_min,lon_max,lat_min,lon_min)
    poly0 = ogr.CreateGeometryFromWkt(wkt1)
    total_area = poly0.GetArea()
    print "Bounding Box {}".format(poly0.ExportToWkt())
    print "Total area is {}".format(total_area)

    # Find location of best overlap with bounding box
    max_frac = 0.0
    for i in range(len(filelist)):
        x,y,trans,proj = saa.read_gdal_file_geo(saa.open_gdal_file(filelist[i]))

        lat_max1 = trans[3]
        lat_min1 = trans[3] + y*trans[5]
        lon_min1 = trans[0]
        lon_max1= trans[0] + x*trans[1]

        wkt2 = "POLYGON ((%s %s, %s %s, %s %s, %s %s, %s %s))" % (lat_min1,lon_min1,lat_max1,lon_min1,lat_max1,lon_max1,lat_min1,lon_max1,lat_min1,lon_min1)

        print "{} Box {}".format(filelist[i],poly0.ExportToWkt())
        poly1 = ogr.CreateGeometryFromWkt(wkt2)
        intersect1 = poly0.Intersection(poly1)
      
        print "{} Int {}".format(filelist[i],intersect1.ExportToWkt())
        area1 = intersect1.GetArea()
        print "area1 is %s" % area1
    
        frac = area1 / total_area
        print "Fraction is {}".format(frac)
        if frac > max_frac:
            max_frac = frac
            max_file = filelist[i]
    if max_frac == 0:
        logging.error("ERROR: None of the input scenes overlap with your area of interest!")
        exit(1)
    loc = filelist.index(max_file)
    
    #
    # Make best overlap image the first in the list
    # This way, when we go to fix projections, we have the correct
    # starting image for our bounding box.
    #
    tmp = filelist[0]
    filelist[0] = filelist[loc]
    filelist[loc] = tmp

def getAscDesc(myxml):
    with open(myxml) as f:
        content = f.readlines()
        for item in content:
            if 'ascending' in item:
                 return "a"
            if 'descending' in item:
                 return "d"

def getXmlFiles(filelist):
    dates = getDates(filelist)
    print "Got dates {}".format(dates)
    print "In directory {}".format(os.getcwd())
    newlist = []
    for date in dates:
        mydir = glob.glob("*{}*-rtc-gamma".format(date))[0]
        myfile = glob.glob("{}/*.iso.xml".format(mydir))[0]
        print "looking for {}".format(myfile)
        newlist.append(myfile)
    return(newlist)
 
def cull_list_by_direction(filelist,direction):
    xmlFiles = getXmlFiles(filelist)
    print "Got xmlfiles {}".format(xmlFiles)
    newlist = []
    for i in range(len(filelist)):
        myfile = filelist[i]
        logging.info("Checking file {} for flight direction".format(myfile))
        ad = getAscDesc(xmlFiles[i])
        logging.info("    Found adflag {}".format(ad))
        if ad == direction:
            logging.info("    Keeping")
            newlist.append(myfile)
        else:
            logging.info("    Discarding")
    return newlist 

def procS1StackRTC(outfile=None,infiles=None,path=None,res=None,filter=False,type='dB-byte',
    scale=[-40,0],clip=None,shape=None,overlap=False,zipFlag=False,leave=False,thresh=0.4,
    font=24,quick=False,amp=False,keep=None):

    # Do some error checking and info printing
    types=['dB','sigma-byte','dB-byte','amp','power']
    if type not in types:
        logging.error("ERROR: unknown output type {}".format(type))
    else:
        logging.info("Creating {} output frames".format(type))

    if keep is not None:
        if keep == 'a':
            logging.info("Keeping only ascending images")
        elif keep == 'd':
            logging.info("Keeping only descending images")
        else:
            logging.error("ERROR: Unknown keep value {} - must be either 'a' or 'a'".format(keep))
            exit(1)

    if shape is not None:
        if not os.path.isfile(shape):
            logging.error("ERROR: Shape file {} does not exist".format(shape))
    	    exit(1)
        if clip is not None:
            logging.error("ERROR: Can not use both shapefile and image clipping options")
            exit(1)
        if overlap:
            logging.error("ERROR: Can not use both shapefile and clip to overlap options")
            exit(1)
    if clip is not None:
        if overlap:
            logging.error("ERROR: Can not use both clip to overlap and image clipping options")
            exit(1)

    # Make the path into an absolute path
    if path is None:
        path = os.getcwd()
    else:
        if path[0] != "/":
            path = os.path.join(os.getcwd(),path)
        if not os.path.isdir(path):
            logging.error("ERROR: Unable to find directory {}".format(path))
            exit(1)

    createCleanDir("TEMP")

    filelist = []
    if infiles is None or len(infiles)==0:
        infiles = None
        if zipFlag:
            logging.info("No input files given, using hyp3 zip files from {}".format(path))
            for myfile in os.listdir(path):
                if ".zip" in myfile:
                    logging.info("    unzipping file {}".format(myfile))
                    zip_ref = zipfile.ZipFile(os.path.join(path,myfile), 'r')
                    zip_ref.extractall("TEMP")
                    zip_ref.close()
        else:
            logging.info("No input files given, using already unzipped hyp3 files in {}".format(path))
            os.chdir("TEMP")
            for myfile in os.listdir(path):
                if os.path.isdir(os.path.join(path,myfile)) and "m-rtc-" in myfile :
                    os.symlink(os.path.join(path,myfile),os.path.basename(myfile))
            os.chdir("..")

        # Now, get the actual list of files
        os.chdir("TEMP")
        filelist = glob.glob("*/*vv*.tif")
        print "FIRST FILE LIST: ".format(filelist)
        # Older zip files don't unzip into their own directories!
        filelist = filelist +  glob.glob("*vv*.tif")
        print "SECOND FILE LIST: ".format(filelist)

        if clip:
            findBestFit(filelist,clip)
        os.chdir("..") 

    else:
        logging.info("Infiles found; using them")
        for myfile in infiles:
            if not os.path.isfile(myfile):
                logging.error("ERROR: Can't find input file {}".format(myfile))
                exit(1)
            if myfile[0] != "/":
                myfile = os.path.join(os.getcwd(),myfile)
            filelist.append(myfile)

    if len(filelist)==0:
        logging.error("ERROR: Found no files to process.")
        exit(1)

    os.chdir("TEMP")

    for i in range(len(filelist)):
        if "/" in filelist[i]:
            os.symlink(filelist[i],os.path.basename(filelist[i]))
            filelist[i] = os.path.basename(filelist[i])
        else:
            if not os.path.isfile(filelist[i]):
                os.symlink("../{}".format(filelist[i]),filelist[i])

    logging.info("List of files to operate on")
    logging.info("{}".format(filelist))

    if keep is not None and infiles is None :
        filelist = cull_list_by_direction(filelist,keep)

    if amp:
        filelist = amp2pwr(filelist)

    if quick:
        filelist = cutStack(filelist,overlap,clip,shape,thresh)
        if len(filelist)!=0:
            if filter:
                filelist = filterStack(filelist)
            if res is not None:
                filelist = changeResStack(filelist,res)
        power_filelist = filelist
    else:
        if filter:
            filelist = filterStack(filelist)
        if res is not None:
            filelist = changeResStack(filelist,res)
        power_filelist = cutStack(filelist,overlap,clip,shape,thresh)

    if len(power_filelist)==0:
        logging.error("ERROR: No images survived the clipping process.")
        if overlap:
            logging.error("ERROR: The image stack does not have overlap.")
        if shape is not None:
            logging.error("ERROR: The image stack does not overlap with the shape file.")
        if clip is not None:       
            logging.error("ERROR: None of the images have sufficient overlap with the area of interest.")
            logging.error("ERROR: You might try lowering the --black value or picking an new area of interest.")
        exit(1)

    dB_filelist = []
    logging.info("Scaling to dB")
    for tmpfile in power_filelist:
        dBfile = create_dB(tmpfile)
        dB_filelist.append(dBfile)
        
    byte_filelist = []
    logging.info("Byte scaling from {} to {}".format(scale[0],scale[1]))
    for tmpfile in dB_filelist:
        bytefile = byteScale(tmpfile,scale[0],scale[1])
        byte_filelist.append(bytefile)

    png_filelist = []
    for myfile in byte_filelist:
        pngFile = myfile.replace(".tif",".png")
        gdal.Translate(pngFile,myfile,format="PNG")
        png_filelist.append(pngFile) 

    # Sort files based upon date and not upon file names!
    cnt = 0
    dates = getDates(png_filelist)        
    date_and_file = []
    for myfile in png_filelist:
        # If using hyp files, annotate with dates
        if infiles is None:
            newFile = "anno_{}".format(myfile)
            execute("convert {FILE} -pointsize {FONT} -gravity north -stroke '#000C' -strokewidth 2 -annotate +0+5 '{DATE}' -stroke none -fill white -annotate +0+5 '{DATE}' {FILE2}". format(FILE=myfile,FILE2=newFile,DATE=dates[cnt],FONT=font)) 
            os.remove(myfile)
        else:
            newFile = myfile

        m = [newFile,dates[cnt]]
        date_and_file.append(m)
        cnt = cnt + 1

    date_and_file.sort(key = lambda row: row[1])

    # Create the animated gif file
    if outfile is not None:
        output = outfile + ".gif"
    else:
        output = "animation.gif"

    string = ""
    for i in range(len(png_filelist)):
        string = string + " " + date_and_file[i][0]

    execute("convert -delay 120 -loop 0 {} {}".format(string,output)) 

    # Create and populate the product directory    
    if outfile is not None:
        prodDir = "../PRODUCT_{}".format(outfile)
    else:
        prodDir = "PRODUCT" 
    createCleanDir(prodDir)

    shutil.move(output,prodDir)

    if type == 'power':
        for myfile in power_filelist:
            shutil.move(myfile,prodDir)
    elif type == 'dB':
        for myfile in dB_filelist:
            shutil.move(myfile,prodDir)
    elif type == 'dB-byte':
        for myfile in byte_filelist:
            shutil.move(myfile,prodDir)
    elif type == 'amp' or type == 'sigma-byte': 
        for myfile in power_filelist:
            ampfile = pwr2amp(myfile)
            if type == 'amp':
                shutil.move(ampfile,prodDir)
            else:
                myrange = get2sigmacutoffs(ampfile)
                newFile = ampfile.replace(".tif","_sigma.tif") 
                gdal.Translate(newFile,ampfile,outputType=gdal.GDT_Byte,scaleParams=[myrange],resampleAlg="average")
                shutil.move(newFile,prodDir)
    
    os.chdir("..")

    # Save unzipped files for later use
    if zipFlag:
        permDir = "hyp3-products-unzipped"
        if not os.path.isdir(permDir):
            os.mkdir(permDir)
        logging.info("Looking in {}".format(os.getcwd()))
        for myfile in glob.glob("TEMP/*"):
            logging.info("    checking file {}".format(myfile))
            if os.path.isdir(myfile):
                newDir = "{}/{}".format(permDir,os.path.basename(myfile))
                logging.info("        file is directory... moving tree {} to {}".format(myfile,newDir))
                if os.path.exists(newDir):
                    shutil.rmtree(newDir)
                shutil.copytree(myfile,newDir)
#            else:
#                logging.info("        file is normal... moving file {} to {}".format(myfile,permDir))
#                shutil.copy(myfile,permDir)

    # Cleanup and exit
    if not leave:
        shutil.rmtree("TEMP")

    print "Done!!!"    

def procS1StackGroupsRTC(outfile=None,infiles=None,path=None,res=None,filter=False,type='dB-byte',
        scale=[-40,0],clip=None,shape=None,overlap=False,zipFlag=False,leave=False,thresh=0.4,
        font=24,quick=False,amp=False,hyp=None,keep=None,group=False):

    if outfile is not None:
        logFile = "{}_run_stats.txt".format(outfile)
    else:
        logFile = "run_stats.txt"
        outfile = "animation"
    logging.basicConfig(filename=logFile,format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler())

    print "\n"
    logging.info("Starting run")
    print "\n"

    if hyp:
        logging.info("Using Hyp3 subscription named {} to download input files".format(hyp))
        username,password = getUsernamePassword()
        api = API(username)
        api.login(password=password)
        download_products(api,sub_name=hyp)
        zipFlag = True
        hyp = None
        path = "hyp3-products"

    if group and (infiles is None or len(infiles)==0):
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

        if zipFlag:
            filelist = glob.glob("{}/S1*.zip".format(path))
        else:
            filelist = []
            print "Path is {}".format(path)
            for myfile in os.listdir(path):
                if os.path.isdir(os.path.join(path,myfile)):
                    filelist.append(myfile)

        if len(filelist)==0:
            print "ERROR: Unable to find zip files"
            exit(1)

        classes, filelists = sortByTime(path,filelist,"rtc")
        for i in range(len(classes)):
            if len(filelists[i])>2:
                mydir = "DATA_{}".format(classes[i])
                createCleanDir(mydir)
                for myfile in filelists[i]:
                    thisDir = "../sorted_{}".format(classes[i])
                    inFile = "{}/{}".format(thisDir,os.path.basename(myfile))
                    outFile = "{}/{}".format(mydir,os.path.basename(myfile))
                    print "Linking file {} to file {}".format(inFile,outFile)
                    os.symlink(inFile,outFile)
                output = outfile + "_" + classes[i]

                procS1StackRTC(outfile=output,infiles=infiles,path=mydir,res=res,filter=filter,
                    type=type,scale=scale,clip=None,shape=None,overlap=True,zipFlag=zipFlag,
                    leave=leave,thresh=thresh,font=font,quick=quick,amp=amp,
                    keep=keep)

                shutil.rmtree(mydir)
    else:
        procS1StackRTC(outfile=outfile,infiles=infiles,path=path,res=res,filter=filter,
            type=type,scale=scale,clip=clip,shape=shape,overlap=overlap,zipFlag=zipFlag,
            leave=leave,thresh=thresh,font=font,quick=quick,amp=amp,
            keep=keep)

    if not leave and group:
        for myfile in glob.glob("sorted_*"):
            shutil.rmtree(myfile)






if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="procS1StackRTC.py",description="Create RTC time series")
    parser.add_argument("infile",nargs="*",help="Input tif filenames, if none given will work from hyp zip files")
    parser.add_argument("-a","--amp",action="store_true",help="Input files are amplitude and not power")
    parser.add_argument("-b","--black",type=float,help="Fraction of black required to remove an image (def 0.4)",default=0.4)
    parser.add_argument("-d","--dBscale",nargs=2,metavar=('upper','lower'),type=float,help="Upper and lower dB for scaling (default -40 0)",default=[-40,0])
    parser.add_argument("-f","--filter",action='store_true',help="Apply speckle filtering")
    parser.add_argument("-g","--group",action='store_true',help="Group files by time before processing into stacks.  Turns on overlap option.")
    parser.add_argument("-k","--keep",choices=['a','d'],help="Switch to keep only ascending or descending images (default is to keep all)")
    parser.add_argument("-l","--leave",action="store_true",help="Leave intermediate files in place")
    parser.add_argument("-m","--magnify",type=int,help="Magnify (set) annotation font size (def 24)",default=24)
    parser.add_argument("-n","--name",type=str,help="Name of the Hyp3 subscription to download for input files")
    parser.add_argument("-o","--outfile",help="Output animation filename")
    parser.add_argument("-p","--path",help="Path to the input files")
    parser.add_argument("-q","--quick",action="store_true",help="Run in quick mode - perform clipping first, then filtering and resampling")
    parser.add_argument("-r","--res",type=float,help="Desired output resolution")
    parser.add_argument("-t","--type",choices=['dB','sigma-byte','dB-byte','amp','power'],help="Output type (default dB-byte)",default="dB-byte")
    parser.add_argument("-z","--zip",action='store_true',help="Start from hyp3 zip files instead of directories")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c","--clip",type=float,metavar=('ULE','ULN','LRE','LRN'),nargs=4,help="Clip output to bounding box (ULE, ULN, LRE, LRN)")
    group.add_argument("-s","--shape",type=str,metavar="shapefile",help="Clip output to shape file (mutually exclusive with -c)")
    group.add_argument("-v","--overlap",action="store_true",help="Clip files to common overlap.  Assumes files are already pixel aligned")
    args = parser.parse_args()

    procS1StackGroupsRTC(outfile=args.outfile,infiles=args.infile,path=args.path,res=args.res,filter=args.filter,
        type=args.type,scale=args.dBscale,clip=args.clip,shape=args.shape,overlap=args.overlap,zipFlag=args.zip,
        leave=args.leave,thresh=args.black,font=args.magnify,quick=args.quick,amp=args.amp,hyp=args.name,
        keep=args.keep,group=args.group)
 
