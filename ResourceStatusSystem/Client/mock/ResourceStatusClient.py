from DIRAC.ResourceStatusSystem.DB.mock.ResourceStatusDB import ResourceStatusDB

from DIRAC.ResourceStatusSystem                             import ValidRes,\
  ValidStatus, ValidStatusTypes, ValidSiteType, ValidServiceType, \
  ValidResourceType 

class ResourceStatusClient( object ):
  
  def __init__( self, serviceIn = None):
    
    if serviceIn is None:
      self.gate = ResourceStatusDB()
    else:
      self.gate = serviceIn
          
  def insertSite( self, siteName, siteType, gridSiteName, **kwargs ):
    return locals()
  def updateSite( self, siteName, siteType, gridSiteName, **kwargs ):
    return locals()
  def getSite( self, siteName = None, siteType = None, gridSiteName = None, 
               **kwargs ):
    return locals()
  def deleteSite( self, siteName = None, siteType = None, gridSiteName = None, 
                  **kwargs ):
    return locals()      
  def getSitePresent( self, siteName = None, siteType = None, 
                      gridSiteName = None, gridTier = None, statusType = None, 
                      status = None, dateEffective = None, reason = None, 
                      lastCheckTime = None, tokenOwner = None, 
                      tokenExpiration = None, formerStatus = None, **kwargs ):
    return locals()

  '''
  ##############################################################################
  # SERVICE FUNCTIONS
  ##############################################################################
  '''
  def insertService( self, serviceName, serviceType, siteName, **kwargs ):
    return locals()
  def updateService( self, serviceName, serviceType, siteName, **kwargs ):
    return locals()
  def getService( self, serviceName = None, serviceType = None, siteName = None, 
                  **kwargs ):
    return locals()
  def deleteService( self, serviceName = None, serviceType = None, 
                     siteName = None, **kwargs ):
    return locals()
  def getServicePresent( self, serviceName = None, siteName = None, 
                         siteType = None, serviceType = None, statusType = None, 
                         status = None, dateEffective = None, reason = None, 
                         lastCheckTime = None, tokenOwner = None, 
                         tokenExpiration = None, formerStatus = None, 
                         **kwargs ):
    return locals()

  '''
  ##############################################################################
  # RESOURCE FUNCTIONS
  ##############################################################################
  '''
  def insertResource( self, resourceName, resourceType, serviceType, siteName,
                      gridSiteName, **kwargs ):
    return locals()
  def updateResource( self, resourceName, resourceType, serviceType, siteName,
                      gridSiteName, **kwargs ):
    return locals()
  def getResource( self, resourceName = None, resourceType = None, 
                   serviceType = None, siteName = None, gridSiteName = None, 
                   **kwargs ):
    return locals()
  def deleteResource( self, resourceName = None, resourceType = None, 
                      serviceType = None, siteName = None, gridSiteName = None, 
                      **kwargs ):
    return locals() 
  def getResourcePresent( self, resourceName = None, siteName = None, 
                          serviceType = None, gridSiteName = None, 
                          siteType = None, resourceType = None, 
                          statusType = None, status = None, 
                          dateEffective = None, reason = None, 
                          lastCheckTime = None, tokenOwner = None, 
                          tokenExpiration = None, formerStatus = None, 
                          **kwargs ):
    return locals()

  '''
  ##############################################################################
  # STORAGE ELEMENT FUNCTIONS
  ##############################################################################
  '''
  def insertStorageElement( self, storageElementName, resourceName, 
                            gridSiteName, **kwargs ):
    return locals()
  def updateStorageElement( self, storageElementName, resourceName, 
                            gridSiteName, **kwargs ):
    return locals()    
  def getStorageElement( self, storageElementName = None, resourceName = None, 
                         gridSiteName = None, **kwargs ):
    return locals()    
  def deleteStorageElement( self, storageElementName = None, 
                            resourceName = None, gridSiteName = None, 
                            **kwargs ):
    return locals()       
  def getStorageElementPresent( self, storageElementName = None, 
                                resourceName = None, gridSiteName = None, 
                                siteType = None, statusType = None, 
                                status = None, dateEffective = None, 
                                reason = None, lastCheckTime = None, 
                                tokenOwner = None, tokenExpiration = None, 
                                formerStatus = None, **kwargs ):
    return locals()

  '''
  ##############################################################################
  # GRID SITE FUNCTIONS
  ##############################################################################
  '''
  def insertGridSite( self, gridSiteName, gridTier, **kwargs ):
    return locals()
  def updateGridSite( self, gridSiteName, gridTier, **kwargs ):
    return locals() 
  def getGridSite( self, gridSiteName = None, gridTier = None, **kwargs ):
    return locals() 
  def deleteGridSite( self, gridSiteName = None, gridTier = None, **kwargs ):        
    return locals()

  '''
  ##############################################################################
  # ELEMENT STATUS FUNCTIONS
  ##############################################################################
  '''
  def insertElementStatus( self, element, elementName, statusType, status, 
                           reason, dateCreated, dateEffective, dateEnd, 
                           lastCheckTime, tokenOwner, tokenExpiration, 
                           **kwargs ): 
    return locals()
  def updateElementStatus( self, element, elementName, statusType, status, 
                           reason, dateCreated, dateEffective, dateEnd, 
                           lastCheckTime, tokenOwner, tokenExpiration, 
                           **kwargs ):
    return locals()
  def getElementStatus( self, element, elementName = None, statusType = None, 
                        status = None, reason = None, dateCreated = None, 
                        dateEffective = None, dateEnd = None, 
                        lastCheckTime = None, tokenOwner = None, 
                        tokenExpiration = None, **kwargs ):
    return locals()
  def deleteElementStatus( self, element, elementName = None, statusType = None, 
                           status = None, reason = None, dateCreated = None, 
                           dateEffective = None, dateEnd = None, 
                           lastCheckTime = None, tokenOwner = None, 
                           tokenExpiration = None, **kwargs ):
    return locals()

  '''
  ##############################################################################
  # ELEMENT SCHEDULED STATUS FUNCTIONS
  ##############################################################################
  '''
  def insertElementScheduledStatus( self, element, elementName, statusType, 
                                    status, reason, dateCreated, dateEffective, 
                                    dateEnd, lastCheckTime, tokenOwner, 
                                    tokenExpiration, **kwargs ): 
    return locals()
  def updateElementScheduledStatus( self, element, elementName, statusType, 
                                    status, reason, dateCreated, dateEffective, 
                                    dateEnd, lastCheckTime, tokenOwner, 
                                    tokenExpiration, **kwargs ):
    return locals()
  def getElementScheduledStatus( self, element, elementName = None, 
                                 statusType = None, status = None, 
                                 reason = None, dateCreated = None, 
                                 dateEffective = None, dateEnd = None, 
                                 lastCheckTime = None, tokenOwner = None, 
                                 tokenExpiration = None, **kwargs ):
    return locals()
  def deleteElementScheduledStatus( self, element, elementName = None, 
                                    statusType = None, status = None, 
                                    reason = None, dateCreated = None,
                                    dateEffective = None, dateEnd = None, 
                                    lastCheckTime = None, tokenOwner = None, 
                                    tokenExpiration = None, **kwargs ):
    return locals()
      
  '''
  ##############################################################################
  # ELEMENT HISTORY FUNCTIONS
  ##############################################################################
  '''
  def insertElementHistory( self, element, elementName, statusType, status, 
                            reason, dateCreated, dateEffective, dateEnd, 
                            lastCheckTime, tokenOwner, tokenExpiration, 
                            **kwargs ): 
    return locals()
  def updateElementHistory( self, element, elementName, statusType, status, 
                            reason, dateCreated, dateEffective, dateEnd, 
                            lastCheckTime, tokenOwner, tokenExpiration, 
                            **kwargs ):
    return locals()
  def getElementHistory( self, element, elementName = None, statusType = None, 
                         status = None, reason = None, dateCreated = None, 
                         dateEffective = None, dateEnd = None, 
                         lastCheckTime = None, tokenOwner = None, 
                         tokenExpiration = None, **kwargs ):
    return locals()
  def deleteElementHistory( self, element, elementName = None, 
                            statusType = None, status = None, reason = None, 
                            dateCreated = None, dateEffective = None, 
                            dateEnd = None, lastCheckTime = None, 
                            tokenOwner = None, tokenExpiration = None, 
                            **kwargs ):
    return locals()  

  '''
  ##############################################################################
  # CS VALID ELEMENTS
  ##############################################################################
  '''
  
  def getValidElements( self ):
    return { 'OK' : True, 'Value' : ValidRes }
  def getValidStatuses( self ):
    return { 'OK' : True, 'Value' : ValidStatus }
  def getValidStatusTypes( self ):  
    return { 'OK' : True, 'Value' : ValidStatusTypes }
  def getValidSiteTypes( self ):
    return { 'OK' : True, 'Value' : ValidSiteType }
  def getValidServiceTypes( self ):
    return { 'OK' : True, 'Value' : ValidServiceType }
  def getValidResourceTypes( self ):
    return { 'OK' : True, 'Value' : ValidResourceType }

  '''
  ##############################################################################
  # EXTENDED FUNCTIONS
  ##############################################################################
  '''

  def addOrModifySite( self, siteName, siteType, gridSiteName ):
    return { 'OK': True, 'Value' : '' }

  def addOrModifyService( self, serviceName, serviceType, siteName ):
    return { 'OK': True, 'Value' : '' }

  def addOrModifyResource( self, resourceName, resourceType, serviceType, 
                           siteName, gridSiteName ):
    return { 'OK': True, 'Value' : '' }

  def addOrModifyStorageElement( self, storageElementName, resourceName, 
                                 gridSiteName ):
    return { 'OK': True, 'Value' : '' }

  def addOrModifyGridSite( self, gridSiteName, gridTier ):
    return { 'OK': True, 'Value' : '' }   

  def modifyElementStatus( self, element, elementName, statusType, 
                           status = None, reason = None, dateCreated = None, 
                           dateEffective = None, dateEnd = None,
                           lastCheckTime = None, tokenOwner = None, 
                           tokenExpiration = None ):
    return { 'OK': True, 'Value' : '' }

  def removeElement( self, element, elementName ):
    return { 'OK': True, 'Value' : '' }

  def getServiceStats( self, siteName, statusType = None ):
    return { 'OK': True, 'Value' : [] }

  def getResourceStats( self, element, name, statusType = None ):
    return { 'OK': True, 'Value' : [] }
 
  def getStorageElementStats( self, element, name, statusType = None ):
    return { 'OK': True, 'Value' : [] }  
  
  def getGeneralName( self, from_element, name, to_element ):
    return { 'OK': True, 'Value' : [] }

  def getGridSiteName( self, granularity, name ):
    return { 'OK': True, 'Value' : [] }

  def getTokens( self, granularity, name = None, tokenExpiration = None, 
                 statusType = None, **kwargs ):
    return { 'OK': True, 'Value' : [] }

  def setToken( self, granularity, name, statusType, reason, tokenOwner, 
                tokenExpiration ):
    return { 'OK': True, 'Value' : '' }

  def setReason( self, granularity, name, statusType, reason ):
    return { 'OK': True, 'Value' : '' }

  def whatIs( self, name ):
    return { 'OK': True, 'Value' : '' }  

  def getStuffToCheck( self, granularity, checkFrequency, **kwargs ):
    return { 'OK': True, 'Value' : [] }

  def getTopology( self ):
    return { 'OK': True, 'Value' : [] }

  def getMonitoredStatus( self, granularity, name ):
    return { 'OK': True, 'Value' : [] }

  def getMonitoredsStatusWeb( self, granularity, selectDict, startItem, 
                              maxItems ):
    return { 'OK': True, 'Value' : {} }
    
               