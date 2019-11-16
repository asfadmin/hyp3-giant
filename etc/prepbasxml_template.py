#!/usr/bin/env python

import tsinsar as ts
import argparse
import numpy as np

if __name__ == '__main__':
    g = ts.TSXML('params')
    g.prepare_sbas_xml(nvalid = 5, netramp=False, atmos='',
                        demerr = False, uwcheck=False, regu=True,
                        filt = 0.1)
    g.writexml('sbas.xml')

