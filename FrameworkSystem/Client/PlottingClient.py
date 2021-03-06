# $HeadURL$

""" PlottingClient is a client of the Plotting Service
"""

__RCSID__ = "$Id$"

import re
import types, tempfile
from DIRAC import S_OK, S_ERROR
from DIRAC.Core.DISET.RPCClient import RPCClient
from DIRAC.Core.DISET.TransferClient import TransferClient

class PlottingClient:

  def __init__( self, rpcClient = False, transferClient = False ):
    self.serviceName = "Framework/Plotting"
    self.rpcClient = rpcClient
    self.transferClient = transferClient

  def __getRPCClient( self ):
    if self.rpcClient:
      return self.rpcClient
    return RPCClient( self.serviceName )

  def __getTransferClient( self ):
    if self.transferClient:
      return self.transferClient
    return TransferClient( self.serviceName )

  def getPlotToMemory( self, plotName ):
    """ Get the prefabricated plot from the service and return it as a string
    """
    transferClient = self.__getTransferClient()
    tmpFile = tempfile.TemporaryFile()
    retVal = transferClient.receiveFile( tmpFile, plotName )
    if not retVal[ 'OK' ]:
      return retVal
    tmpFile.seek( 0 )
    data = tmpFile.read()
    tmpFile.close()
    return S_OK( data )

  def getPlotToFile( self, plotName, fileName ):
    """ Get the prefabricated plot from the service and store it in a file
    """
    transferClient = self.__getTransferClient()
    try:
      destFile = file( fileName, "wb" )
    except Exception, e:
      return S_ERROR( "Can't open file %s for writing: %s" % ( fileName, str( e ) ) )
    retVal = transferClient.receiveFile( destFile, plotName )
    if not retVal[ 'OK' ]:
      return retVal
    destFile.close()
    return S_OK( fileName )

  def graph( self, data, fname = False, *args, **kw ):
    """ Generic method to obtain graphs from the Plotting service. The requested
        graphs are completely described by their data and metadata
    """

    client = self.__getRPCClient()
    plotMetadata = {}
    for arg in args:
      if type( arg ) == types.DictType:
        plotMetadata.update( arg )
      else:
        return S_ERROR( 'Non-dictionary non-keyed argument' )
    plotMetadata.update( kw )
    result = client.generatePlot( data, plotMetadata )
    if not result['OK']:
      return result

    plotName = result['Value']
    if fname and fname != 'Memory':
      result = self.getPlotToFile( plotName, fname )
    else:
      result = self.getPlotToMemory( plotName )

    return result

  def barGraph( self, data, file, *args, **kw ):
    return self.graph( data, file, plot_type = 'BarGraph', statistics_line = True, *args, **kw )

  def lineGraph( self, data, file, *args, **kw ):
    return self.graph( data, file, plot_type = 'LineGraph', statistics_line = True, *args, **kw )

  def cumulativeGraph( self, data, file, *args, **kw ):
    return self.graph( data, file, plot_type = 'LineGraph', cumulate_data = True, *args, **kw )

  def pieGraph( self, data, file, *args, **kw ):
    prefs = {'xticks':False, 'yticks':False, 'legend_position':'right'}
    return self.graph( data, file, prefs, plot_type = 'PieGraph', *args, **kw )

  def qualityGraph( self, data, file, *args, **kw ):
    prefs = {'plot_axis_grid':False}
    return self.graph( data, file, prefs, plot_type = 'QualityMapGraph', *args, **kw )

  def textGraph( self, text, file, *args, **kw ):
    prefs = {'text_image':text}
    return self.graph( {}, file, prefs, *args, **kw )

  def histogram( self, data, file, bins, *args, **kw ):
    try:
      from pylab import hist
    except:
      return S_ERROR( "No pylab module available" )
    values, vbins, patches = hist( data, bins )
    histo = dict( zip( vbins, values ) )
    span = ( max( data ) - min( data ) ) / float( bins ) * 0.98
    return self.graph( histo, file, plot_type = 'BarGraph', span = span, statistics_line = True, *args, **kw )
