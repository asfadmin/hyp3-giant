#!/usr/bin/env python
#
# Thomas Logan, 9/14/18
# Adopted from code written by Piyush Agram
#
import os
import glob
import sys
import argparse
import numpy as np
import shutil
import logging
import zipfile
from osgeo import gdal
import saa_func_lib as saa

def getPixSize(fi):
    (x1,y1,t1,p1) = saa.read_gdal_file_geo(saa.open_gdal_file(fi))
    return (t1[1])

def getCorners(fi):
    (x1,y1,t1,p1) = saa.read_gdal_file_geo(saa.open_gdal_file(fi))
    ullon1 = t1[0]
    ullat1 = t1[3]
    lrlon1 = t1[0] + x1*t1[1]
    lrlat1 = t1[3] + y1*t1[5]
    return (ullon1,ullat1,lrlon1,lrlat1)

def getOverlap(coords,fi):
    (x1,y1,t1,p1) = saa.read_gdal_file_geo(saa.open_gdal_file(fi))

    ullon1 = t1[0]
    ullat1 = t1[3]
    lrlon1 = t1[0] + x1*t1[1]
    lrlat1 = t1[3] + y1*t1[5]

    ullon2 = coords[0]
    ullat2 = coords[1]
    lrlon2 = coords[2]
    lrlat2 = coords[3]

    ullat = min(ullat1,ullat2)
    ullon = max(ullon1,ullon2)
    lrlat = max(lrlat1,lrlat2)
    lrlon = min(lrlon1,lrlon2)

    return (ullon,ullat,lrlon,lrlat)


def get_bbox_isce(intdir):

    this_pass = 0
    for myfile in glob.glob(os.path.join(intdir, '*/merged/filt_topophase.unw.geo')):
        if this_pass == 0:
            coords = getCorners(myfile)
        else:
            coords = getOverlap(coords,myfile)
        this_pass = this_pass + 1
        
    return(coords[3],coords[1],coords[0],coords[2])

def make_descriptor_file(vrtdir):

    f = open("descriptor.txt","w")
    for myfile in glob.glob("{}/*_unw.tif".format(vrtdir)):
        base = os.path.basename(myfile)
        mdate = base[0:8]
        print "Found mdate of {}".format(mdate)
        sdate = base[9:17]
        print "Found sdate of {}".format(sdate)
        pfile = base
        cfile = base.replace("_unw","_cor")
        f.write("{} {} {} {} 0.0\n".format(mdate,sdate,pfile,cfile))
    f.close()

def unzip_file(infile):

    zip_ref = zipfile.ZipFile(infile,'r')
    string = zip_ref.namelist()
    if "/" in string[0]:
        print "File {} has a directory".format(infile)
        zip_ref.extractall(".")
        zip_ref.close()    
    else:
       print "File {} has no directory".format(infile)
       dirname = infile.replace(".unw_geo.zip","") + "/merged"
       os.makedirs(dirname)
       zip_ref.extractall(dirname)
       zip_ref.close()   


def prepGIAnT(bbox=None,refpt=None,intdir=None):

    logging.info("***********************************************************************************")
    logging.info("               Preparing ARIA phase and coherence files")
    logging.info("***********************************************************************************")

    #Directory to get interferograms from
    if intdir is None:
        intdir = os.getcwd()

    logging.info("Getting input file from directory {}".format(intdir))

    for myfile in glob.glob("S1-IFG_*.zip"):
        unzip_file(myfile)

    # If no bounding box given, determine one
    if bbox is None:
        bbox = get_bbox_isce(intdir)
   
    logging.info("Using bounding box of {}".format(bbox))

    # Set the reference pixel location
    if refpt is None:
        refpt = []
        refpt.append(bbox[0]+(bbox[1]-bbox[0])/2)
        refpt.append(bbox[2]+(bbox[3]-bbox[2])/2)

    refpix = [int(3600*(bbox[1]-refpt[0])), int(3600*(refpt[1]-bbox[2]))]

    logging.info("Using reference point of {}".format(refpt))
    logging.info("Using reference pixel of {}".format(refpix))

    #Check if GIAnT dir exists. Create it if not.
    prepdir = "./GIAnT"
    if os.path.isdir(prepdir):
        print("{0} directory already exists".format(prepdir))
    else:
        os.mkdir(prepdir) 

    #Check if VRT dir exists. Create it if not.
    vrtdir = "./DATA"
    if os.path.isdir(vrtdir):
        print("{0} directory already exists".format(vrtdir))
    else:
        os.mkdir(vrtdir)

    ####Prepare ifg.list
    ifglist=os.path.join(prepdir, 'ifg.list')
    if os.path.exists(ifglist):
        print("Deleting old {0}".format(ifglist))
        os.remove(ifglist)

    #Crop cmd tmpl
#    cmdunwtmpl  = 'gdal_translate -of ENVI -b 2 -projwin {0} {1} {2} {3}'.format(bbox[2], bbox[1], bbox[3], bbox[0])
#    cmdcortmpl  = 'gdal_translate -of ENVI -b 1 -projwin {0} {1} {2} {3}'.format(bbox[2], bbox[1], bbox[3], bbox[0])

    cmdunwtmpl  = 'gdal_translate -b 2 -projwin {0} {1} {2} {3}'.format(bbox[2], bbox[1], bbox[3], bbox[0])
    cmdcortmpl  = 'gdal_translate -b 1 -projwin {0} {1} {2} {3}'.format(bbox[2], bbox[1], bbox[3], bbox[0])

    pairs = []
    #####Get list of IFGS
    fid = open(ifglist, 'w')
    for dirf in glob.glob(os.path.join(intdir, '*/merged/filt_topophase.unw.geo')):
        bname = os.path.dirname(dirf)
        vals = dirf.split(os.path.sep)

        root = vals[-3]
        master = root.split('-')[1].split('_')[-1][0:8]
        slave = root.split('-')[2][0:8]
        tstamp = root.split('-')[2][9:15]
        vroot = master + '_' + slave

        fid.write("{0}   {1}   0.0   S1\n".format(master,slave))

        ###Create crop vrt for cor file
        cmd = "{0}  {1} {2}".format(cmdcortmpl, os.path.abspath(os.path.join(bname, 'phsig.cor.geo.vrt')), os.path.join(vrtdir, vroot + '_cor.tif'),1)
        status = os.system(cmd)
        if status:
            print(cmd)
            raise Exception('Error processing cor for {0} from dir {1}'.format(vroot, bname))


        ###Create crop vrt for unw file
        cmd = "{0}  {1} {2}".format(cmdunwtmpl, os.path.abspath(os.path.join(bname, 'filt_topophase.unw.geo.vrt')), os.path.join(vrtdir, vroot + '_unw.tif'),2)
        status = os.system(cmd)
        if status:
            print(cmd)
            raise Exception('Error processing cor for {0} from dir {1}'.format(vroot, bname))    

    fid.close()

    #####Make the descriptor file
    make_descriptor_file(vrtdir)

    #####Create example.rsc
    exampleVRT = os.path.join(vrtdir, vroot+'_unw.tif')
    ds  = gdal.Open(exampleVRT, gdal.GA_ReadOnly)

    rdict = {}
    rdict['WIDTH'] = ds.RasterXSize
    rdict['FILE_LENGTH'] = ds.RasterYSize
    rdict['HEADING_DEG'] = -12.0
    rdict['WAVELENGTH'] = 0.05546576

    rdict['CENTER_LINE_UTC'] = int(tstamp[0:2])*3600 + int(tstamp[2:4])*60 + int(tstamp[4:6])

    ds = None

    exampleRSC = os.path.join(prepdir, 'example.rsc')
    if os.path.exists(exampleRSC):
        print("Deleting old {0}".format(exampleRSC))
        os.remove(exampleRSC)

    
    fid = open(exampleRSC, 'w')
    for key, value in rdict.items():
        fid.write('{0:20}       {1}\n'.format(key, value))
    fid.close()

    #######Create userfn.py
    reldir = os.path.relpath(vrtdir, prepdir)
    uspy = """
#!/usr/bin/env python3
import os 

def makefnames(dates1, dates2, sensor):
    dirname = '{0}'
    root = os.path.join(dirname, dates1+'_'+dates2)
    iname = root + '_unw.bin'
    cname = root + '_cor.bin'
    return iname, cname""".format(reldir)

    fid = open(os.path.join(prepdir,'userfn.py'), 'w')
    fid.write(uspy)
    fid.close() 


    ##########Create prepxml.py

    xmlCode = """

#!/usr/bin/env python3

import tsinsar as ts
import argparse
import numpy as np

if __name__ == '__main__':

    ######Prepare the data.xml
    g = ts.TSXML('data')
    g.prepare_data_xml('example.rsc', proc='RPAC',
                       xlim=[0,{0}], ylim=[0, {1}],
                       rxlim = [{2},{3}], rylim=[{4},{5}],
                       latfile='', lonfile='', hgtfile='',
                       inc = 34., cohth=0.2, chgendian='False',
                       unwfmt='GRD', corfmt='GRD')
    g.writexml('data.xml')

""".format(rdict['WIDTH'], rdict['FILE_LENGTH'],
           refpix[1]-5, refpix[1]+5,   #Reference region in range
           refpix[0]-5, refpix[0]+5)    #Reference region in azimuth

    fid = open(os.path.join(prepdir, 'prepdataxml.py'),'w')
    fid.write(xmlCode)
    fid.close()
   
    ######Prepare the sbas.xml file
    xmlCode  = """
#!/usr/bin/env python3

import tsinsar as ts
import argparse
import numpy as np

if __name__ == '__main__':
    g = ts.TSXML('params')
    g. prepare_sbas_xml(nvalid = {0}, netramp=False, atmos='',
                        demerr = False, uwcheck=False, regu=True,
                        filt = 0.1)
    g.writexml('sbas.xml')
""".format(60)

    fid = open(os.path.join(prepdir, 'prepsbasxml.py'), 'w')
    fid.write(xmlCode)
    fid.close()

    return("descriptor.txt",rdict['CENTER_LINE_UTC'])

if __name__ == '__main__':

    parser = argparse.ArgumentParser(prog='prepGIAnT.py',
        description='Prepare a stack of interferograms from ARIA to run through GIANT')
    parser.add_argument("-b","--bbox",type=float,metavar=('minLat','matLat','minLon','maxLon'),nargs=4,
        help="Clip output to bounding box, default is common overlap")
    parser.add_argument("-r","--refpt",type=float,nargs=2,metavar=('lat','lon'),
        help="Set reference point (default is center of image)")
    parser.add_argument("-p","--path",help="Path to input interferograms")
    args = parser.parse_args()

    logFile = "prepGIAnT_{}_log.txt".format(os.getpid())
    logging.basicConfig(filename=logFile,format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.info("Starting run")

    prepGIAnT(args.bbox,args.refpt)
