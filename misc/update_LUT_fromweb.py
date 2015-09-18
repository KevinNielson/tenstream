#!/usr/bin/env python

import netCDF4 as NC
import numpy as np
import sys
import os
import shutil


def filename_from_url(url):
    import urlparse
    return os.path.basename(urlparse.urlsplit(url)[2])

def list_ftpdir(url):
    import ftplib
    import urlparse

    parsed_uri = urlparse.urlparse(url)
    domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)    

    ftp = ftplib.FTP()
    ftp.connect( parsed_uri.netloc )
    ftp.login()

    ftp.cwd( os.path.dirname( parsed_uri.path ) )

    files = []

    try:
        files = ftp.nlst()
    except ftplib.error_perm, resp:
        if str(resp) == "550 No files found":
            print "No files in this directory"
        else:
            raise
    
#    print 'Server Repository has the following files in it: \n'
#    for f in files:
#        print f
#
#    print '\n Maybe you want one of those? \n'
    return files

def get_ftp_file(url):
    import ftplib
    import urlparse
    import tempfile

    parsed_uri = urlparse.urlparse(url)
    domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)    

    ftp = ftplib.FTP()
    ftp.connect( parsed_uri.netloc )
    ftp.login()

    ftp.cwd( os.path.dirname( parsed_uri.path ) )

    fdst = tempfile.NamedTemporaryFile()
    print 'Downloading file from',url,' => ',fdst.name
    ftp.retrbinary('RETR %s' % os.path.basename( parsed_uri.path ), fdst.write)
    fdst.file.flush()

    ftp.quit()
    return fdst

def copy_nc_var(Din, varname, Dout):
    invar = Din.variables[varname]

    #Copy dimensions
    for dname, the_dim in Din.dimensions.iteritems():
      print 'Copy dimension:', dname, len(the_dim)
      Dout.createDimension(dname, len(the_dim) if not the_dim.isunlimited() else None)
    
    # Copy variables
    outVar = Dout.createVariable(invar.name, invar.datatype, invar.dimensions)

    # Copy variable attributes
    outVar.setncatts({k: invar.getncattr(k) for k in invar.ncattrs()})

    outVar[:] = invar[:]

def merge_nc_var(server,server_tol, local,local_tol):
    cond_server = server_tol[:] <  local_tol[:] # 1 if server better than local 
    cond_local  = server_tol[:] >  local_tol[:] # 1 if local  better than server
    cond_same   = server_tol[:] == local_tol[:] # 1 if same

    Nlocal  = np.sum(cond_local)
    Nserver = np.sum(cond_server)
    Nsame   = np.sum(cond_same)
    print '    Using {0:} values from server and {1:} from local table :: same: {2:}'.format(Nserver,Nlocal,Nsame)
    if Nlocal>0:
        print '      ATTENTION ::: If you have a lot of better coeffs than are available at the Server please send them to fabian@jakub.com'
    
    new     = local    [:]
    new_tol = local_tol[:]

    new    [cond_server] = server    [:][cond_server]
    new_tol[cond_server] = server_tol[:][cond_server]

    print '    max  tol ( server,local ) :: {0:e15.4} {1:e15.4} '.format( np.max(server_tol[:]), np.max(local_tol[:])  ), ' :: new', np.max(new_tol[:])
    print '    mean tol ( server,local ) :: {0:e15.4} {1:e15.4} '.format( np.mean(server_tol[:]), np.mean(local_tol[:])), ' :: new', np.mean(new_tol[:])
    local[:] = new[:]
    local_tol[:] = new_tol[:]
    

def merge_LUT(serverLUT, LUT):
    print 'merging LUT {0:} ==> {1:}'.format(serverLUT,LUT)

    Dserver = NC.Dataset(serverLUT, mode='r')
    if os.path.isfile(LUT):
      fmode='a'
    else:
      print 'Creating new NC file:',LUT
      fmode='w'

#    Dlocal  = NC.Dataset(LUT, mode=fmode, format="NETCDF3_CLASSIC")
#    Dlocal  = NC.Dataset(LUT, mode='a', format="NETCDF3_64BIT")
#    Dlocal  = NC.Dataset(LUT, mode=fmode, format="NETCDF4_CLASSIC")
    Dlocal  = NC.Dataset(LUT, mode=fmode, format="NETCDF4")

#    print 'Server LUTs',Dserver.variables.keys()
#    print 'Local  LUTs',Dlocal.variables.keys()
    print ''

    # Check if we can copy some tables
    for k in  Dserver.variables.keys():
        if k not in Dlocal.variables:
            print 'Found var which is not in local LUT... copying it over from server LUT :: ',k
            copy_nc_var(Dserver, k, Dlocal)
        else:
            print 'already exists in local LUT :: ',k

    # Check if we should merge some values bc. server version has better tolerances
    for k in Dserver.variables.keys():
        if k.endswith('S') or k.endswith('T'):

            print '\nMerging NC Variable',k, k+'_tol'
            server     = Dserver.variables[k]
            server_tol = Dserver.variables[k+'_tol']
            local      = Dlocal.variables [k]
            local_tol  = Dlocal.variables [k+'_tol']
            merge_nc_var(server,server_tol, local,local_tol)


    Dserver.close()
    Dlocal.close()
    
    
def update_LUT(LUTpath, LUTserver):

    path,LUTname = os.path.split(LUTpath)

    try: # download LUT from ftp
        url = 'ftp://'+LUTserver+'/'+LUTname
        serverLUTfile = get_ftp_file(url)

    except Exception,e:
        print 'Error occured when we tried download LUT with name:',LUTname
        print e

        availfiles = list_ftpdir(url)
        print 'Server Repository has the following files in it: \n'
        for f in availfiles:
            print f
    
        print '\n Maybe you want one of those? \n'
        return

    merge_LUT(serverLUTfile.name, LUTpath)

    serverLUTfile.close() # finally close temp file and with that, delete it

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Input parameters for LUT web downloader')
    parser.add_argument('LUTpath', type=str, help='LUT file which should be loaded/merged')
    parser.add_argument('-LUTserver', type=str, help='LUTserver which should be queried for LUTs', default='ftp.meteo.physik.uni-muenchen.de/public/TenStream_LUT/')
    parser.add_argument('-list', action='store_const',const=True, help='list all available files at the server', default=False)
    args = parser.parse_args()

    if args.list:
      availfiles = list_ftpdir('ftp://'+args.LUTserver)
      for f in availfiles:
        print f
      sys.exit(0)


    update_LUT(args.LUTpath, args.LUTserver)

