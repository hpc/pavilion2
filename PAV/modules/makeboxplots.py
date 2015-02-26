#!/usr/bin/env python


#  ###################################################################
#
#  Disclaimer and Notice of Copyright 
#  ==================================
#
#  Copyright (c) 2015, Los Alamos National Security, LLC
#  All rights reserved.
#
#  Copyright 2015. Los Alamos National Security, LLC. 
#  This software was produced under U.S. Government contract 
#  DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), 
#  which is operated by Los Alamos National Security, LLC for 
#  the U.S. Department of Energy. The U.S. Government has rights 
#  to use, reproduce, and distribute this software.  NEITHER 
#  THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES 
#  ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY 
#  FOR THE USE OF THIS SOFTWARE.  If software is modified to 
#  produce derivative works, such modified software should be 
#  clearly marked, so as not to confuse it with the version 
#  available from LANL.
#
#  Additionally, redistribution and use in source and binary 
#  forms, with or without modification, are permitted provided 
#  that the following conditions are met:
#  -  Redistributions of source code must retain the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer. 
#  -  Redistributions in binary form must reproduce the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer in the documentation 
#     and/or other materials provided with the distribution. 
#  -  Neither the name of Los Alamos National Security, LLC, 
#     Los Alamos National Laboratory, LANL, the U.S. Government, 
#     nor the names of its contributors may be used to endorse 
#     or promote products derived from this software without 
#     specific prior written permission.
#   
#  THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC 
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
#  IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS 
#  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, 
#  OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, 
#  OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY 
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR 
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT 
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY 
#  OF SUCH DAMAGE.
#
#  ###################################################################



""" Make box plots from the output of the get_results command"""


# Input:  stdin stream of lines with, hopefully, trend data lines included
#  ex. of a valid line is:
#    Test4.2x32(10 1024) jid(109959) 2014-09-04T08:43:22-0600 avg_iterTime 0.002910 sec
# Output: Should be a messaged indicating where output plot files reside

import sys
import re
import os
import datetime
from numpy import loadtxt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import logging


def get_subdirectories( dir):
    return [name for name in os.listdir( dir )
        if os.path.isdir(os.path.join(dir, name))]

def makesingleboxplot(thisdirname, subdirname, thisfilename):

    # print "thisdir ", thisdirname
    maxnodeint = 1
    firsttime = 0
    firstdigit = 1
    segname=[]
    ylabelunits = []
    idecpoint = -1
    ivallen = 0
    iseform = -1
    decdigits = 2

    tablefmtstring = "%d %d "


    thisdatafile = thisdirname + "/" + thisfilename
    datafile = open( thisdatafile )
    for line in datafile:
        thisnode=[]
        del thisnode[:]
        tud,jud,tid,mname,pname2,nodename,trest = line.split(' ',6)

        nfile = thisdirname + "/" + ''.join(nodename)
        if firsttime < 1:

            firstdigit = re.search("\d", ''.join(nodename))
            firstdigit = firstdigit.start()
            # print firstdigit, ''.join(nodename)
            firsttime = 1
            for i in xrange( 0, firstdigit  ):
                # segname[i] = nodename[i]
                segname.append(  nodename[i] )
            segname.append( '%' )

            segname.append( '0' )
            nlen = len( nodename ) - firstdigit
            segname.append( "%d" % nlen )
            # segname.append( len( nodename ) - firstdigit + 1 )
            segname.append( 'd' )
            # print "trest is ", trest
            trestlen = len( trest )
            spdigit = -1
            spdigit = trest.find(' ')
            # spdigit = ".join(trest).find(' ')

            valstring = []
            # if spdigit > -1:
                # for j in xrange( 0, spdigit - 1):
                # for j in xrange( 0, spdigit ):
                    # valstring.append( trest[j] )
            # else:
                # valstring = trest
            valstring = trest.split()[0]

            # print "valstring is ", valstring
            # if spdigit > 0:
                # print "spdigit is not 0, can make units string ", spdigit
                # for j in xrange( spdigit + 1, trestlen - 1 ):
                    # ylabelunits.append( trest[j] )

                # print "ylabelunits is ", ylabelunits

            if len( trest.split() ) > 1:
                ylabelunits = trest.split()[1]
                # print "ylabelunits is ", ylabelunits
            # idecpoint = valstring.find( '.')
            # idecpoint = str(valstring).find( '.')
            ivallen = len( valstring )
            idecpoint = -1
            for j in xrange( 0, ivallen ):
                if valstring[j] == '.':
                    idecpoint = j
                    break

            iseform = str(valstring).find( 'e' )
            decdigits = 2
            # print " idecpoint ", idecpoint, " ivallen ", ivallen, " iseform ", iseform,  " decdigits ", decdigits
            if idecpoint > -1:
                # decdigits = decdigits + ivallen - idecpoint - 2
                decdigits = ivallen - idecpoint + 1

            if iseform > -1:
                vfmtstring = "%%.%de %%.%de %%.%de %%.%de " % (decdigits, decdigits, decdigits - 2, decdigits - 2)
            else:
                vfmtstring = "%%.%df %%.%df %%.%df %%.%df\n" % (decdigits, decdigits, decdigits - 2, decdigits - 2)
            tablefmtstring = tablefmtstring + vfmtstring
            # print tablefmtstring
            # print  segname
        tnode = int( nodename[firstdigit:] )
        if tnode > maxnodeint:
            maxnodeint = tnode


        t2restlen = len( trest )
        vspdigit = -1
        vspdigit = trest.find(' ')


        tvalstring = []
        if vspdigit > -1:
                # for j in xrange( 0, spdigit - 1):
            for j in xrange( 0, vspdigit ):
                tvalstring.append( trest[j] )
        else:
            tvalstring = trest
        nodefile = open( nfile, "a" )

        # print "printing to file ", nfile, " ", trest.split()[0]
        # print >> nodefile, trest,
        # print >> nodefile, ''.join( tvalstring )
        print >> nodefile, trest.split()[0]

        # print >> nodefile, str( tvalstring )
        nodefile.close()



	# Begin processing a list of files in the current directory, complicated list of lists
    chtodir = "cd " + thisdirname
    os.system(chtodir)
    # print "issued command ", chtodir

    fstring = ''.join(segname)  # "wf%03d"
    maxnodenum = maxnodeint + 1  # 620
    # print maxnodeint
    if len( ylabelunits) < 1:
        ytitle = "Performance (MB/sec)"
    else:
        ytitle = "Performance " + "(" + str(ylabelunits) + ")"

    ctitle = subdirname + " Performance Boxplot"

    fname={}
    dlist=[]
    hpldata=[]
    tmarks=[]
    tname=[]
    nnum=[]
    nticks=0

    for x in range(1,maxnodenum):
        fname[x] = fstring % (x)
        # print "x ", x
        # print fname[x]

        # if  os.path.isfile(fname[x]) :
        if os.path.isfile( thisdirname + "/" + fname[x]):
            nticks += 1
            dlist.append( loadtxt( thisdirname + "/" + fname[x]) )
            nnum.append( x )
            if (x % 2) == 0:
                tmarks.append("%d" % (x))
            else:
                tmarks.append('')
    # print "Dlistlength is ",  len(dlist )
    # print dlist

    dmeans=[]
    for j in dlist:
        dmeans.append( j.mean() )


    dmins=[]
    for j in dlist:
        dmins.append( j.min() )

    dmaxs=[]
    for j in dlist:
        dmaxs.append( j.max() )

    dsamps=[]
    for j in dlist:
        dsamps.append( j.size )

    dstds=[]
    for j in dlist:
        dstds.append(j.std())

    nodetable=[]
    nodetable = zip(nnum, dsamps, dmeans, dstds, dmins, dmaxs)
    # print nodetable
    # for i in nodetable:
        # print i

    # print "tablefmtstring ", tablefmtstring
    tablename = thisdirname + "/FinalDataTable.txt"
    tablefile = open(tablename, "w")
    for i in nodetable:
        # print >> tablefile, i
        # print >> tablefile, '%d %d %24f %.4f %.2f %.2f', i
        # print >> tablefile, '%d %d %.4f %.4f %.2f %.2f', i[0], i[1], i[2], i[3], i[4], i[5]
        # tablefile.write( '%d %d %.4f %.4f %.2f %.2f\n' % ( i[0], i[1], i[2], i[3], i[4], i[5] ))
        tablefile.write( tablefmtstring % (i[0], i[1], i[2], i[3], i[4], i[5]))
    tablefile.close()


    nodemeans=[]
    nodemeans = zip( nnum, dmeans )

    # print nodemeans
    nodemeans.sort(key=lambda x: x[1])
    xtickmarks=[]

    # try to add a null tick mark at beginning
    xtickmarks.append('')
    # end try

    for i, v in nodemeans:
        #	xname = "mu%04d" % (i)
        xname = fstring % i
        xtickmarks.append(xname)

    dlist.sort(key=lambda a: a.mean())
    plt.figure()
    # boxplot(multidata)
    # print dlist
    if len(dlist) < 1:
        return 0

    # break
    plt.boxplot(dlist)
    # boxplot(hpldata2)
    plt.xlabel('Node')
    # ylabel('Performance (GFlops)')
    plt.ylabel(ytitle)
    # title("Mustang Quarantined HPL with Proper Affinities Set Performance Variation")
    plt.title(ctitle)

    nnodes = len( dlist )

    adjustedwidth = nnodes / 100.0 * 10.0 ;
    if adjustedwidth < 10.0:
        adjustedwidth = 10.0

    # print 'Nodes collected for ', nnodes, ' adjusted width is ', adjustedwidth

    ticktable=[]
    for k in xtickmarks:
        ticktable.append( k )


    plt.xticks( range( len( xtickmarks)), rotation=90, fontsize=6 )
    plt.xticks( range( len( ticktable)), xtickmarks,  rotation=90, fontsize=6 )

    fig = matplotlib.pyplot.gcf()
    # fig.set_size_inches(10.0,7.0)
    fig.set_size_inches(adjustedwidth,7.0)

    # show()
    plotname = thisdirname + "/" + subdirname + "Boxplot.png"
    # plt.savefig('BoxplotGraph.png', dpi=150 )
    plt.savefig(plotname, dpi=150)

    return nnodes


def main():
    sub_dir = "Boxplots-" + datetime.datetime.now().strftime('%m-%d-%YT%H:%M:%S:%f')

    # if "HOME" in self.output_dir_root:
    # root = os.environ['HOME']
    # else:
    # root = self.output_dir_roo
    root = os.environ['PV_RESULT_ROOT']
    #root = "/usr/projects/splunk/results/prr/wf"
    output_dir = root + "/Boxplots/" + sub_dir

    # self.logger.info(self.lh + " Make Boxplots directory: " + output_dir)
    try:
        os.umask(0o002)
        os.makedirs(output_dir, 0o755)
    except OSError:
        print " Error creating Boxplots directory : \n\t" + output_dir
        #    self.logger.info(self.lh + " Error creating Boxplots directory : \n\t" + output_dir)
        output_dir = ''
        pass

    print "Boxplots dir -> " + output_dir
    print "  View hint: 'find Boxplots_dir -name \*.png -exec showimage {} \;'"
    AllDataFile = output_dir + "/AllDataFile.txt"

    prelimout = open(AllDataFile, "w")
    # print "Making box plots with data from:"
    for line in sys.stdin:
        searchObj = re.search(r'jid\(', line, re.M|re.I)
        # isreportable = line.find( "+" )
        isreportable = -1
        nwords = len( line.split() )
        if nwords > 4:
            isreportable = line.split()[3].find( '+' )
            # print " wordis ", line.split()[3], " is ", isreportable

            wlen = len( line.split()[3] )
            if wlen - isreportable < 2:
                isreportable = -1
            # print " wordis ", line.split()[3], " is ", isreportable
        if searchObj and isreportable > 1:
            # if searchObj:
            # Should do work here, see correct output above
            # print line,  # this line for debug purpose
            tname= []
            restline= []
            newline= []

            jidx = line.find(" jid(")
            for i in xrange(0,jidx ):
                if line[i] == ' ':
                    tname.append("-")
                else:
                    tname.append(line[i])
            firstrep = 0
            for i in xrange(jidx, len(line) - 1):
                if line[i] == '+':
                    if firstrep == 0:
                        restline.append(" ")
                        firstrep = 1
                    else:
                        restline.append(line[i])
                else:
                    restline.append(line[i])

            print >> prelimout, ''.join(tname), ''.join(restline)
    prelimout.close()

    alltests = open(AllDataFile, "r")
    for line in alltests:
        thisname=[]
        del thisname[:]

        jidx = line.find(" jid(")
        for i in xrange(1,jidx - 1):
            if line[i] == '.':
                break
            else:
                thisname.append( line[i])

        tud, jud, tid, pname, pname2, trest = line.split(' ', 5)
        tdirectory = output_dir + "/" + ''.join(thisname) + "-" + ''.join(pname2)
        if not os.path.isdir(tdirectory):
            mkdircmd = "mkdir " + tdirectory
            os.system( mkdircmd )
        thisfname = tdirectory + "/TableRes.txt"
        thisfile = open(thisfname, "a")
        print >> thisfile, line,
        thisfile.close()



    # [subdirList[0] for subdirList in os.walk(output_dir)]
    # subdirList = os.listdir( output_dir )
    subdirList = get_subdirectories(output_dir)
    ndone = 0
    ntodo = len( subdirList )
    print "Start Processing Directory List ", subdirList
    for dres in subdirList:
        subdirname = ''.join( dres )
        procthisdir = output_dir + "/" + ''.join( dres)
        # procthisdir = ''.join( dres)
        # print "procdir is ", procthisdir
        # if os.path.isdir( procthisdir ):
        nodesfound = makesingleboxplot(procthisdir,subdirname, "TableRes.txt" )
        print "Finished Processing Directory ", ndone, " Percent done ", (float(ndone + 1) / float(ntodo) ) * 100.0, \
        " UniqueNodesFound ", nodesfound
        ndone += 1



# def makesingleboxplot():
        # return "made boxplot"

if __name__ == '__main__':
    # pass entire command line to main except for the command name
    main()
    sys.exit()

