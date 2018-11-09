#!/usr/bin/env python
import os 

def makefnames(dates1, dates2, sensor):
    dirname = '/home/talogan/SENTINEL_IFM/COCHISE'
    root = os.path.join(dirname, dates1+'_'+dates2)
    iname = os.path.join(root,'merged/filt_topophase.unw.geo')
    cname = os.path.join(root,'merged/phsig.cor.geo')
    return iname, cname

