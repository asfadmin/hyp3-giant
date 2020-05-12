#!/usr/bin/env python
###############################################################################
# makePNG.py 
#
# Project:  APD INSAR 
# Purpose:  Make a group of downsized PNGs from an HDF5 file 
#          
# Author:   Aidan Myers
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
from scipy.stats import *
from scipy.ndimage import *
import numpy
import h5py
import os, sys
import matplotlib
matplotlib.use('Agg') 
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import logging

def mkMovie(h5file,layer,mm=None):
    source = h5py.File(h5file)
    imgarray = source["{}".format(layer)][()]
    images = numpy.split(imgarray, imgarray.shape[0])

    if mm is not None:
        logging.debug("mm is {}, values are {} and {}".format(mm,mm[0],mm[1]))

    mini = 0
    maxi = 0
    img_list = []
    shape = (0,0)
    for scene in images:
        img = numpy.reshape(scene,scene.shape[1:])
        img = img[:,~(numpy.all(numpy.isnan(img), axis=0))]
        img = img[~(numpy.all(numpy.isnan(img), axis=1))]
        
        reduced = interpolation.zoom(img, .25, order=1)
         
        if mm is None: 
            reduced[numpy.isnan(reduced)] = 0
            if numpy.min(reduced) < mini:
                mini = numpy.min(reduced)
            if numpy.max(reduced) > maxi:
                maxi = numpy.max(reduced)

        img_list.append((img,reduced))
        shape = img.shape
        img = []

    if mm is not None:
        mini = float(mm[0])
        maxi = float(mm[1])

    logging.info("Scaling from %s to %s" % (mini, maxi))

    filelist = []
    for (i, images) in enumerate(img_list):
        (fsimg, rsimg) = images

        # Generates ordinary png
#        mpimg.imsave('frame' + str(i).zfill(3) + '.png', rsimg, cmap='RdYlBu', vmin = mini,vmax = maxi,dpi=100) 

        # Writes Binary
        fsimg.tofile('frame' + str(i).zfill(3) + '.flat')

        # Generates png with scalebar   
        fig_im = plt.imshow(fsimg, cmap='RdYlBu',vmin=mini,vmax=maxi)
        plt.colorbar(orientation = 'horizontal',shrink = .5,pad=.05)
        plt.axis('off')
        name = "{}_{}_{}.png".format(h5file.replace(".h5",""),layer,str(i).zfill(3))
        plt.savefig(name, bbox_inches="tight")
        plt.clf()
        fsimg = []
        rsimg = []
        filelist.append(name)

    return filelist

def main():
 i = sys.argv[1]
 mkMovie(i, layer='error')

if __name__ == "__main__":
  main()
