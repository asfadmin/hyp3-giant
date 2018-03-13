#!/usr/bin/python
import os
import shutil

for myfile in os.listdir("."):
    if "zip" in myfile:
         newName = myfile.split("?")[0]
         print "New Name is {}".format(newName)
         shutil.move(myfile,newName)

