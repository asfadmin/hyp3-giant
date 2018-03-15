
import os
from os.path import expanduser

def getUsernamePassword():
    home = expanduser("~")
    fileName = home + '/.netrc'
    if not os.path.isfile(fileName):
        print "ERROR: No .netrc file found in {}".format(home)
        print ""
        print "You will need a .netrc file in order to downoad the HyP3 data."
        print "Please see the documentation or the webpage https://disc.gsfc.nasa.gov/data-access"
        print "for information on how to create an Earthdata login and a .netrc file"
        print ""
        exit(1)
    f = open(fileName,"r")
    username = None
    password = None
    for line in f:
        if "login" in line:
            username = line.split()[1]
            print "Username is {}".format(username)
        if "password" in line:
            password = line.split()[1]
            print "Found password"
    if username is None or password is None:
        print "ERROR: Unable to get username or password from .netrc file"
        exit(1)
    return username, password

