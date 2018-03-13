#!/usr/bin/env python

import tsinsar as ts
import argparse
import numpy as np

if __name__ == '__main__':

    ######Prepare the data.xml
    g = ts.TSXML('data')
    g.prepare_data_xml('example.rsc', proc='RPAC',
                       xlim=[0,5005], ylim=[0, 6049],
                       rxlim = [2445,2455], rylim=[2225,2235],
                       latfile='', lonfile='', hgtfile='',
                       inc = 29., cohth=0.2, chgendian='False',
                       unwfmt='FLT', corfmt='FLT')
    g.writexml('data.xml')

