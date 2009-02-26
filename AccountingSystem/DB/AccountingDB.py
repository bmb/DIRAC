# $Header: /tmp/libdirac/tmp.stZoy15380/dirac/DIRAC3/DIRAC/AccountingSystem/DB/AccountingDB.py,v 1.5 2009/02/26 16:15:02 acasajus Exp $
__RCSID__ = "$Id: AccountingDB.py,v 1.5 2009/02/26 16:15:02 acasajus Exp $"

import datetime, time
import types
import threading
import os, os.path
import re
import DIRAC
from DIRAC.Core.Base.DB import DB
from DIRAC import S_OK, S_ERROR, gLogger, gMonitor, gConfig
from DIRAC.Core.Utilities import List, ThreadSafe, Time, DEncode
from DIRAC.Core.Utilities.ThreadPool import ThreadPool

gSynchro = ThreadSafe.Synchronizer()

class AccountingDB(DB):

  def __init__( self, maxQueueSize = 10 ):
    DB.__init__( self, 'AccountingDB','Accounting/AccountingDB', maxQueueSize )
    self.maxBucketTime = 604800 #1 w
    self.autoCompact = False
    self.dbCatalog = {}
    self.dbBucketsLength = {}
    maxParallelInsertions = self.getCSOption( "ParallelRecordInsertions", maxQueueSize )
    self.__threadPool = ThreadPool( 2, maxParallelInsertions )
    self.__threadPool.daemonize()
    self.catalogTableName = self.__getTableName( "catalog", "Types" )
    self._createTables( { self.catalogTableName : { 'Fields' : { 'name' : "VARCHAR(64) UNIQUE NOT NULL",
                                                          'keyFields' : "VARCHAR(256) NOT NULL",
                                                          'valueFields' : "VARCHAR(256) NOT NULL",
                                                          'bucketsLength' : "VARCHAR(256) NOT NULL",
                                                       },
                                             'PrimaryKey' : 'name'
                                           }
                        }
                      )
    self.__loadCatalogFromDB()
    gMonitor.registerActivity( "registeradded",
                               "Register added",
                               "Accounting",
                               "entries",
                               gMonitor.OP_ACUM )
    gMonitor.registerActivity( "insertiontime",
                               "Record insertion time",
                               "Accounting",
                               "seconds",
                               gMonitor.OP_MEAN )
    self.__registerTypes()

  def __loadTablesCreated( self ):
    result = self._query( "show tables" )
    if not result[ 'OK' ]:
      return result
    return S_OK( [ f[0] for f in result[ 'Value' ] ] )

  def autoCompactDB( self ):
    self.autoCompact = True
    th = threading.Thread( target = self.__periodicAutoCompactDB )
    th.setDaemon( 1 )
    th.start()

  def __periodicAutoCompactDB(self):
    compactTime = datetime.time( hour = 4, minute = 30, second = 2 )
    while self.autoCompact:
      nct = Time.dateTime()
      if nct.hour >= compactTime.hour:
        nct = nct + datetime.timedelta( days = 1 )
      nct = nct.replace( hour = compactTime.hour,
                         minute = compactTime.minute,
                         second = compactTime.second )
      self.log.info( "Next db compaction will be at %s" % nct )
      sleepTime = Time.toEpoch( nct ) - Time.toEpoch()
      time.sleep( sleepTime )
      self.compactBuckets()

  def __registerTypes( self ):
    """
    Register all types
    """
    retVal = gConfig.getSections( "/DIRAC/Setups" )
    if not retVal[ 'OK' ]:
      return S_ERROR( "Can't get a list of setups: %s" % retVal[ 'Message' ] )
    setupsList = retVal[ 'Value' ]
    typeRE = re.compile( ".*[a-z1-9]\.py$" )
    for typeFile in os.listdir( os.path.join( DIRAC.rootPath, "DIRAC", "AccountingSystem", "Client", "Types" ) ):
      if typeRE.match( typeFile ):
        for setup in setupsList:
          pythonName = typeFile.replace( ".py", "" )
          typeName = "%s_%s" % ( setup, pythonName )
          if pythonName != "BaseAccountingType":
            self.log.info( "Trying to register %s type for setup %s" % ( typeName, setup ) )
            try:
              typeModule = __import__( "DIRAC.AccountingSystem.Client.Types.%s" % pythonName,
                                       globals(),
                                       locals(), pythonName )
              typeClass  = getattr( typeModule, pythonName )
            except Exception, e:
              self.log.error( "Can't load type %s: %s" % ( typeName, str(e) ) )
              continue
            typeDef = typeClass().getDefinition()
            #dbTypeName = "%s_%s" % ( setup, typeName )
            definitionKeyFields, definitionAccountingFields, bucketsLength = typeDef[1:]
            #If already defined check the similarities
            if typeName in self.dbCatalog:
              bucketsLength.sort()
              if bucketsLength != self.dbBucketsLength[ typeName ]:
                bucketsLength = self.dbBucketsLength[ typeName ]
                self.log.error( "Bucket length has changed for type %s" % typeName )
              keyFields = [ f[0] for f in definitionKeyFields ]
              if keyFields != self.dbCatalog[ typeName ][ 'keys' ]:
                keyFields = self.dbCatalog[ typeName ][ 'keys' ]
                self.log.error( "Definition fields have changed for type %s" % typeName )
              valueFields = [ f[0] for f in definitionAccountingFields ]
              if valueFields != self.dbCatalog[ typeName ][ 'values' ]:
                valueFields = self.dbCatalog[ typeName ][ 'values' ]
                self.log.error( "Accountable fields have changed for type %s" % typeName )
            #Try to re register to check all the tables are there
            retVal = self.registerType( typeName, definitionKeyFields,
                                        definitionAccountingFields, bucketsLength )
            if not retVal[ 'OK' ]:
              self.log.error( "Can't register type %s:%s" % ( typeName, retVal[ 'Message' ] ) )
    return S_OK()

  def __loadCatalogFromDB(self):
    retVal = self._query( "SELECT `name`, `keyFields`, `valueFields`, `bucketsLength` FROM `%s`" % self.catalogTableName )
    if not retVal[ 'OK' ]:
      raise Exception( retVal[ 'Message' ] )
    for typesEntry in retVal[ 'Value' ]:
      typeName = typesEntry[0]
      keyFields = List.fromChar( typesEntry[1], "," )
      valueFields = List.fromChar( typesEntry[2], "," )
      bucketsLength = DEncode.decode( typesEntry[3] )[0]
      self.__addToCatalog( typeName, keyFields, valueFields, bucketsLength )

  def getWaitingRecordsLifeTime( self ):
    """
    Get the time records can live in the IN tables without no retry
    """
    return self.getCSOption( "RecordMaxWaitingTime", 86400 )

  def loadPendingRecords(self):
    """
      Load all records pending to insertion and generate threaded jobs
    """
    self.log.info( "Loading pending records for insertion" )
    pending = 0
    for typeName in self.dbCatalog:
      self.log.info( "Checking %s" % typeName )
      sqlTableName = self.__getTableName( "in", typeName )
      sqlFields = [ 'id' ] + self.dbCatalog[ typeName ][ 'typeFields' ]
      sqlCond = "taken = 0 or TIMESTAMPDIFF( SECOND, takenSince, UTC_TIMESTAMP() ) > %s" % self.getWaitingRecordsLifeTime()
      result = self._query( "SELECT %s FROM `%s`  WHERE %s ORDER BY id ASC LIMIT 1000" % ( ", ".join( [ "`%s`" % f for f in sqlFields ] ),
                                                                                     sqlTableName,
                                                                                     sqlCond ) )
      if not result[ 'OK' ]:
        self.log.error( "Error when trying to get pending records", "for %s : %s" % ( typeName, result[ 'Message' ] ) )
        return result
      self.log.info( "Got %s pending requests for type %s" % ( len( result[ 'Value' ] ), typeName ) )
      dbData = result[ 'Value' ]
      idList = [ str( r[0] ) for r in dbData ]
      #If nothing to do, continue
      if not idList:
        continue
      result = self._update( "UPDATE `%s` SET taken=1, takenSince=UTC_TIMESTAMP() WHERE id in (%s)" % ( sqlTableName,
                                                                                                           ", ".join( idList ) ) )
      if not result[ 'OK' ]:
        self.log.error( "Error when trying set state to waiting records", "for %s : %s" % ( typeName, result[ 'Message' ] ) )
        return result
      for record in dbData:
        id =         record[ 0 ]
        startTime =  record[ -2 ]
        endTime =    record[ -1 ]
        valuesList = list( record[ 1:-2 ] )
        self.__threadPool.generateJobAndQueueIt( self.__insertFromINTable ,
                                             args = ( id, typeName, startTime, endTime, valuesList, Time.toEpoch() ) )
        pending += 1
    self.log.info( "Got %s pending requests for all types" % pending )
    return S_OK()

  def __getTableName( self, tableType, typeName, keyName = None ):
    """
    Generate table name
    """
    if not keyName:
      return "ac_%s_%s" % ( tableType, typeName )
    elif tableType == "key" :
      return "ac_%s_%s_%s" % ( tableType, typeName, keyName )
    else:
      raise Exception( "Call to __getTableName with tableType as key but with no keyName" )

  def __addToCatalog( self, typeName, keyFields, valueFields, bucketsLength ):
    """
    Add type to catalog
    """
    self.log.verbose( "Adding to catalog type %s" % typeName, "with length %s" % str( bucketsLength ) )
    self.dbCatalog[ typeName ] = { 'keys' : keyFields , 'values' : valueFields, 'typeFields' : [], 'bucketFields' : [] }
    self.dbCatalog[ typeName ][ 'typeFields' ].extend( keyFields )
    self.dbCatalog[ typeName ][ 'typeFields' ].extend( valueFields )
    self.dbCatalog[ typeName ][ 'bucketFields' ] = list( self.dbCatalog[ typeName ][ 'typeFields' ] )
    self.dbCatalog[ typeName ][ 'typeFields' ].extend( [ 'startTime', 'endTime' ] )
    self.dbCatalog[ typeName ][ 'bucketFields' ].extend( [  'entriesInBucket', 'startTime', 'bucketLength' ] )
    self.dbBucketsLength[ typeName ] = bucketsLength
    #ADRI: TEST COMPACT BUCKETS
    #self.dbBucketsLength[ typeName ] = [ ( 86400, 3600 ), ( 15552000, 86400 ), ( 31104000, 604800 ) ]

  @gSynchro
  def changeBucketsLength( self, typeName, bucketsLength ):
    if not typeName in self.dbCatalog:
      return S_ERROR( "%s is not a valid type name" % typeName )
    bucketsLength.sort()
    bucketsEncoding = DEncode.encode( bucketsLength )
    retVal = self._update( "UPDATE `%s` set bucketsLength = '%s' where name = '%s'" % ( self.catalogTableName,
                                                                              bucketsEncoding,
                                                                              typeName ) )
    if not retVal[ 'OK' ]:
      return retVal
    self.dbBucketsLength[ typeName ] = bucketsLength
    return self.regenerateBuckets( typeName )

  @gSynchro
  def registerType( self, name, definitionKeyFields, definitionAccountingFields, bucketsLength ):
    """
    Register a new type
    """
    result = self.__loadTablesCreated()
    if not result[ 'OK' ]:
      return result
    tablesInThere = result[ 'Value' ]
    keyFieldsList = []
    valueFieldsList = []
    for t in definitionKeyFields:
      keyFieldsList.append( t[0] )
    for t in definitionAccountingFields:
      valueFieldsList.append( t[0] )
    for field in definitionKeyFields:
      if field in valueFieldsList:
        return S_ERROR( "Key field %s is also in the list of value fields" % field )
    for field in definitionAccountingFields:
      if field in keyFieldsList:
        return S_ERROR( "Value field %s is also in the list of key fields" % field )
    for bucket in bucketsLength:
      if type( bucket ) != types.TupleType:
        return S_ERROR( "Length of buckets should be a list of tuples" )
      if len( bucket ) != 2:
        return S_ERROR( "Length of buckets should have 2d tuples" )
    updateDBCatalog = True
    if name in self.dbCatalog:
      updateDBCatalog = False
    tables = {}
    for key in definitionKeyFields:
      keyTableName = self.__getTableName( "key", name, key[0] )
      if keyTableName not in tablesInThere:
        self.log.info( "Table for key %s has to be created" % key[0] )
        tables[ keyTableName  ] = { 'Fields' : { 'id' : 'INTEGER NOT NULL AUTO_INCREMENT',
                                                 'value' : '%s UNIQUE NOT NULL' % key[1]
                                               },
                                    'UniqueIndexes' : { 'valueindex' : [ 'value' ] },
                                    'PrimaryKey' : 'id'
                                  }
    #Registering type
    fieldsDict = {}
    bucketFieldsDict = {}
    inbufferDict = { 'id' : 'INTEGER NOT NULL AUTO_INCREMENT' }
    indexesDict = {}
    uniqueIndexFields = []
    for field in definitionKeyFields:
      indexesDict[ "%sIndex" % field[0] ] = [ field[0] ]
      uniqueIndexFields.append( field[ 0 ] )
      fieldsDict[ field[0] ] = "INTEGER NOT NULL"
      bucketFieldsDict[ field[0] ] = "INTEGER NOT NULL"
      inbufferDict[ field[0] ] = field[1] + " NOT NULL"
    for field in definitionAccountingFields:
      fieldsDict[ field[0] ] = field[1] + " NOT NULL"
      bucketFieldsDict[ field[0] ] = "DECIMAL(30,10) NOT NULL"
      inbufferDict[ field[0] ] = field[1] + " NOT NULL"
    fieldsDict[ 'startTime' ] = "INT UNSIGNED NOT NULL"
    fieldsDict[ 'endTime' ] = "INT UNSIGNED NOT NULL"
    bucketFieldsDict[ 'entriesInBucket' ] = "DECIMAL(30,10) NOT NULL"
    bucketFieldsDict[ 'startTime' ] = "INT UNSIGNED NOT NULL"
    inbufferDict[ 'startTime' ] = "INT UNSIGNED NOT NULL"
    inbufferDict[ 'endTime' ] = "INT UNSIGNED NOT NULL"
    inbufferDict[ 'taken' ] = "TINYINT(1) DEFAULT 1 NOT NULL"
    inbufferDict[ 'takenSince' ] = "DATETIME NOT NULL"
    uniqueIndexFields.append( 'startTime' )
    bucketFieldsDict[ 'bucketLength' ] = "MEDIUMINT UNSIGNED NOT NULL"
    uniqueIndexFields.append( 'bucketLength' )
    bucketTableName = self.__getTableName( "bucket", name )
    if bucketTableName not in tablesInThere:
      tables[ bucketTableName ] = { 'Fields' : bucketFieldsDict,
                                      'Indexes' : indexesDict,
                                      'UniqueIndexes' : { 'UniqueConstraint' : uniqueIndexFields }
                                    }
    typeTableName = self.__getTableName( "type", name )
    if typeTableName not in tablesInThere:
      tables[ typeTableName ] = { 'Fields' : fieldsDict,
                                    'Indexes' : indexesDict,
                                  }
    inTableName = self.__getTableName( "in", name )
    if inTableName not in tablesInThere:
      tables[ inTableName ] = { 'Fields' : inbufferDict,
                                    'Indexes' : { 'idIndex' : [ 'id' ] },
                                    'PrimaryKey' : 'id'
                                  }
    if tables:
      retVal = self._createTables( tables )
      if not retVal[ 'OK' ]:
        self.log.error( "Can't create type %s: %s" % ( name, retVal[ 'Message' ] ) )
        return S_ERROR( "Can't create type %s: %s" % ( name, retVal[ 'Message' ] ) )
    if updateDBCatalog:
      bucketsLength.sort()
      bucketsEncoding = DEncode.encode( bucketsLength )
      self._insert( self.catalogTableName,
                    [ 'name', 'keyFields', 'valueFields', 'bucketsLength' ],
                    [ name, ",".join( keyFieldsList ), ",".join( valueFieldsList ), bucketsEncoding ] )
      self.__addToCatalog( name, keyFieldsList, valueFieldsList, bucketsLength )
    self.log.info( "Registered type %s" % name )
    return S_OK()

  def getRegisteredTypes( self ):
    """
    Get list of registered types
    """
    retVal = self._query( "SELECT `name`, `keyFields`, `valueFields`, `bucketsLength` FROM `%s`" % self.catalogTableName )
    if not retVal[ 'OK' ]:
      return retVal
    typesList = []
    for typeInfo in retVal[ 'Value' ]:
      typesList.append( [ typeInfo[0],
                          List.fromChar( typeInfo[1] ),
                          List.fromChar( typeInfo[2] ),
                          DEncode.decode( typeInfo[3] )
                        ]
                      )
    return S_OK( typesList )

  def getKeyValues( self, typeName, condDict, connObj = False ):
    """
    Get all values for a given key field in a type
    """
    keyValuesDict = {}

    keyTables = []
    sqlCond = []
    mainTable = "`%s`" % self.__getTableName( "bucket", typeName )
    typeKeysList = self.dbCatalog[ typeName ][ 'keys' ]

    for keyName in condDict:
      if keyName in typeKeysList:
        keyTable = "`%s`" % self.__getTableName( "key", typeName, keyName )
        if not keyTable in keyTables:
          keyTables.append( keyTable )
        sqlCond.append( "%s.id = %s.`%s`" % ( keyTable, mainTable, keyName ) )
        for value in condDict[ keyName ]:
          sqlCond.append( "%s.value = %s" % ( keyTable, self._escapeString( value )[ 'Value' ] ) )

    for keyName in typeKeysList:
      keyTable = "`%s`" % self.__getTableName( "key", typeName, keyName )
      allKeyTables = keyTables
      if not keyTable in allKeyTables:
        allKeyTables = list( keyTables )
        allKeyTables.append( keyTable )
      cmd = "SELECT DISTINCT %s.value FROM %s" % ( keyTable, ", ".join( allKeyTables ) )
      if sqlCond:
        sqlValueLink = "%s.id = %s.`%s`" % ( keyTable, mainTable, keyName )
        cmd += ", %s WHERE %s AND %s" % ( mainTable, sqlValueLink, " AND ".join( sqlCond ) )
      retVal = self._query( cmd, conn = connObj )
      if not retVal[ 'OK' ]:
        return retVal
      keyValuesDict[ keyName ] = [ r[0] for r in retVal[ 'Value' ] ]

    return S_OK( keyValuesDict )

  @gSynchro
  def deleteType( self, typeName ):
    """
    Deletes a type
    """
    if typeName not in self.dbCatalog:
      return S_ERROR( "Type %s does not exist" % typeName )
    self.log.info( "Deleting type", typeName )
    tablesToDelete = []
    for keyField in self.dbCatalog[ typeName ][ 'keys' ]:
      tablesToDelete.append( "`%s`" % self.__getTableName( "key", typeName, keyField ) )
    tablesToDelete.insert( 0, "`%s`" % self.__getTableName( "type", typeName ) )
    tablesToDelete.insert( 0, "`%s`" % self.__getTableName( "bucket", typeName ) )
    retVal = self._query( "DROP TABLE %s" % ", ".join( tablesToDelete ) )
    if not retVal[ 'OK' ]:
      return retVal
    retVal = self._update( "DELETE FROM `%s` WHERE name='%s'" % ( self.__getTableName( "catalog", "Types" ), typeName ) )
    del( self.dbCatalog[ typeName ] )
    return S_OK()

  def __getIdForKeyValue( self, typeName, keyName, keyValue, conn = False ):
    """
      Finds id number for value in a key table
    """
    retVal = self._query( "SELECT `id` FROM `%s` WHERE `value`='%s'" % ( self.__getTableName( "key", typeName, keyName ),
                                                                         keyValue ), conn = conn )
    if not retVal[ 'OK' ]:
      return retVal
    if len( retVal[ 'Value' ] ) > 0:
      return S_OK( retVal[ 'Value' ][0][0] )
    return S_ERROR( "Key id %s for value %s does not exist although it shoud" % ( keyName, keyValue ) )

  def __addKeyValue( self, typeName, keyName, keyValue ):
    """
      Adds a key value to a key table if not existant
    """
    keyTable = self.__getTableName( "key", typeName, keyName )
    if type( keyValue ) != types.StringType:
      keyValue = str( keyValue )
    retVal = self.__getIdForKeyValue( typeName, keyName, keyValue )
    if retVal[ 'OK' ]:
      return retVal
    else:
      retVal = self._getConnection()
      if not retVal[ 'OK' ]:
        return retVal
      connection = retVal[ 'Value' ]
      self.log.info( "Value %s for key %s didn't exist, inserting" % ( keyValue, keyName ) )
      retVal = self._insert( keyTable, [ 'id', 'value' ], [ 0, keyValue ], connection )
      if not retVal[ 'OK' ] and retVal[ 'Message' ].find( "Duplicate key" ) == -1:
        return retVal
      return self.__getIdForKeyValue( typeName, keyName, keyValue, connection )
    return S_OK( keyId )

  def calculateBucketLengthForTime( self, typeName, now, when ):
    """
    Get the expected bucket time for a moment in time
    """
    for granuT in self.dbBucketsLength[ typeName ]:
      nowBucketed = now - now % granuT[1]
      dif = max( 0,  nowBucketed - when )
      if dif <= granuT[0]:
        return granuT[1]
    return self.maxBucketTime

  def calculateBuckets( self, typeName, startTime, endTime ):
    """
    Magic function for calculating buckets between two times and
    the proportional part for each bucket
    """
    nowEpoch = int( Time.toEpoch( Time.dateTime() ) )
    bucketTimeLength = self.calculateBucketLengthForTime( typeName, nowEpoch, startTime )
    currentBucketStart = startTime - startTime % bucketTimeLength
    if startTime == endTime:
      return [ ( currentBucketStart,
                 1,
                 bucketTimeLength ) ]
    buckets = []
    totalLength = endTime - startTime
    while currentBucketStart < endTime:
      start = max( currentBucketStart, startTime )
      end = min( currentBucketStart + bucketTimeLength, endTime )
      proportion = float( end - start ) / totalLength
      buckets.append( ( currentBucketStart,
                        proportion,
                        bucketTimeLength ) )
      currentBucketStart += bucketTimeLength
      bucketTimeLength = self.calculateBucketLengthForTime( typeName, nowEpoch, currentBucketStart )
    return buckets

  def insertRecordThroughQueue( self, typeName, startTime, endTime, valuesList ):
    """
    Insert a record in the intable to be really insterted afterwards
    """
    self.log.verbose( "Adding RAW record", "for type %s [%s -> %s]" % ( typeName, Time.fromEpoch( startTime ), Time.fromEpoch( endTime ) ) )
    if not typeName in self.dbCatalog:
      return S_ERROR( "Type %s has not been defined in the db" % typeName )
    sqlFields = [ 'id', 'taken', 'takenSince' ] + self.dbCatalog[ typeName ][ 'typeFields' ]
    sqlValues = [ '0', '1', 'UTC_TIMESTAMP()' ] + valuesList + [ startTime, endTime ]
    retVal = self._insert( self.__getTableName( "in", typeName ),
                           sqlFields,
                           sqlValues)
    if not retVal[ 'OK' ]:
      return retVal
    id = retVal[ 'lastRowId' ]
    self.__threadPool.generateJobAndQueueIt( self.__insertFromINTable ,
                                             args = ( id, typeName, startTime, endTime, valuesList, Time.toEpoch() ) )
    return retVal

  def __insertFromINTable( self, id, typeName, startTime, endTime, valuesList, insertionEpoch ):
    """
    Do the real insert and delete from the in buffer table
    """
    result = self.insertRecordDirectly( typeName, startTime, endTime, valuesList )
    if not result[ 'OK' ]:
      self._update( "UPDATE `%s` SET taken=0 WHERE id=%s" % ( self.__getTableName( "in", typeName ), id ) )
      self.log.error( "Can't insert row", result[ 'Message' ] )
      return result
    result = self._update( "DELETE FROM `%s` WHERE id=%s" % ( self.__getTableName( "in", typeName ), id ) )
    if not result[ 'OK' ]:
      self.log.error( "Can't delete row from the IN table", result[ 'Message' ] )
    #TODO HERE
    gMonitor.addMark( "insertiontime", Time.toEpoch() - insertionEpoch )
    return result

  def insertRecordDirectly( self, typeName, startTime, endTime, valuesList ):
    """
    Add an entry to the type contents
    """
    gMonitor.addMark( "registeradded", 1 )
    self.log.info( "Adding record", "for type %s [%s -> %s]" % ( typeName, Time.fromEpoch( startTime ), Time.fromEpoch( endTime ) ) )
    if not typeName in self.dbCatalog:
      return S_ERROR( "Type %s has not been defined in the db" % typeName )
    #Discover key indexes
    for keyPos in range( len( self.dbCatalog[ typeName ][ 'keys' ] ) ):
      keyName = self.dbCatalog[ typeName ][ 'keys' ][ keyPos ]
      keyValue = valuesList[ keyPos ]
      retVal = self.__addKeyValue( typeName, keyName, keyValue )
      if not retVal[ 'OK' ]:
        return retVal
      self.log.verbose( "Value %s for key %s has id %s" % ( keyValue, keyName, retVal[ 'Value' ] ) )
      valuesList[ keyPos ] = retVal[ 'Value' ]
    insertList = list( valuesList )
    insertList.append( startTime )
    insertList.append( endTime )
    retVal = self._getConnection()
    if not retVal[ 'OK' ]:
      return retVal
    connObj = retVal[ 'Value' ]
    retVal = self._insert( self.__getTableName( "type", typeName ),
                           self.dbCatalog[ typeName ][ 'typeFields' ],
                           insertList,
                           conn = connObj )
    if not retVal[ 'OK' ]:
      return retVal
    #HACK: One more record to split in the buckets to be able to count total entries
    valuesList.append(1)
    retVal = self.__startTransaction( connObj )
    if not retVal[ 'OK' ]:
      return retVal
    retVal =self.__splitInBuckets( typeName, startTime, endTime, valuesList, connObj = connObj )
    if not retVal[ 'OK' ]:
      self.__rollbackTransaction( connObj )
      return retVal
    return self.__commitTransaction( connObj )

  def __splitInBuckets( self, typeName, startTime, endTime, valuesList, connObj = False ):
    """
    Bucketize a record
    """
    #Calculate amount of buckets
    buckets = self.calculateBuckets( typeName, startTime, endTime )
    #Separate key values from normal values
    numKeys = len( self.dbCatalog[ typeName ][ 'keys' ] )
    keyValues = valuesList[ :numKeys ]
    valuesList = valuesList[ numKeys: ]
    self.log.verbose( "Splitting entry", " in %s buckets" % len( buckets ) )
    for bucketInfo in buckets:
      bucketStartTime = bucketInfo[0]
      bucketProportion = bucketInfo[1]
      bucketLength = bucketInfo[2]
      #INSERT!
      retVal = self.__insertBucket( typeName,
                                    bucketStartTime,
                                    bucketLength,
                                    keyValues,
                                    valuesList, bucketProportion, connObj = connObj )
      #If OK insert is successful
      if retVal[ 'OK' ]:
        continue
      #if not OK and NOT duplicate keys error then real error
      if retVal[ 'Message' ].find( 'Duplicate entry' ) == -1:
        return retVal
      #Duplicate keys!!. If that's the case..
      #Update!
      retVal = self.__updateBucket( typeName,
                                    bucketStartTime,
                                    bucketLength,
                                    keyValues,
                                    valuesList, bucketProportion, connObj = connObj )
      if not retVal[ 'OK' ]:
        return retVal
    return S_OK()

  def getBucketsDef( self, typeName ):
    return self.dbBucketsLength[ typeName ]

  def __generateSQLConditionForKeys( self, typeName, keyValues ):
    """
    Generate sql condition for buckets, values are indexes to real values
    """
    realCondList = []
    for keyPos in range( len( self.dbCatalog[ typeName ][ 'keys' ] ) ):
      keyField = self.dbCatalog[ typeName ][ 'keys' ][ keyPos ]
      keyValue = keyValues[ keyPos ]
      retVal = self._escapeString( keyValue )
      if not retVal[ 'OK' ]:
        return retVal
      keyValue = retVal[ 'Value' ]
      realCondList.append( "`%s`.`%s` = %s" % ( self.__getTableName( "bucket", typeName ), keyField, keyValue ) )
    return " AND ".join( realCondList )

  def __getBucketFromDB( self, typeName, startTime, bucketLength, keyValues, connObj = False ):
    """
    Get a bucket from the DB
    """
    tableName = self.__getTableName( "bucket", typeName )
    sqlFields = []
    for valueField in self.dbCatalog[ typeName ][ 'values' ]:
      sqlFields.append( "`%s`.`%s`" % ( tableName, valueField ) )
    sqlFields.append( "`%s`.`entriesInBucket`" % ( tableName ) )
    cmd = "SELECT %s FROM `%s`" % ( ", ".join( sqlFields ), self.__getTableName( "bucket", typeName ) )
    cmd += " WHERE `%s`.`startTime`='%s' AND `%s`.`bucketLength`='%s' AND " % (
                                                                              tableName,
                                                                              startTime,
                                                                              tableName,
                                                                              bucketLength )
    cmd += self.__generateSQLConditionForKeys( typeName, keyValues )
    return self._query( cmd, conn = connObj )

  def __updateBucket( self, typeName, startTime, bucketLength, keyValues, bucketValues, proportion, connObj = False ):
    """
    Update a bucket when coming from the raw insert
    """
    tableName = self.__getTableName( "bucket", typeName )
    cmd = "UPDATE `%s` SET " % tableName
    sqlValList = []
    for pos in range( len( self.dbCatalog[ typeName ][ 'values' ] ) ):
      valueField = self.dbCatalog[ typeName ][ 'values' ][ pos ]
      value = bucketValues[ pos ]
      fullFieldName = "`%s`.`%s`" % ( tableName, valueField )
      sqlValList.append( "%s=%s+(%s*%s)" % ( fullFieldName, fullFieldName, value, proportion ) )
    sqlValList.append( "`%s`.`entriesInBucket`=`%s`.`entriesInBucket`+(%s*%s)" % ( tableName,
                                                                                    tableName,
                                                                                    bucketValues[-1],
                                                                                    proportion ) )
    cmd += ", ".join( sqlValList )
    cmd += " WHERE `%s`.`startTime`='%s' AND `%s`.`bucketLength`='%s' AND " % (
                                                                            tableName,
                                                                            startTime,
                                                                            tableName,
                                                                            bucketLength )
    cmd += self.__generateSQLConditionForKeys( typeName, keyValues )
    return self._update( cmd, conn = connObj )

  def __insertBucket( self, typeName, startTime, bucketLength, keyValues, bucketValues, proportion, connObj = False ):
    """
    Insert a bucket when coming from the raw insert
    """
    sqlFields = [ '`startTime`', '`bucketLength`', '`entriesInBucket`' ]
    sqlValues = [ startTime, bucketLength, "(%s*%s)" % ( bucketValues[-1], proportion )]
    for keyPos in range( len( self.dbCatalog[ typeName ][ 'keys' ] ) ):
      sqlFields.append( "`%s`" % self.dbCatalog[ typeName ][ 'keys' ][ keyPos ] )
      sqlValues.append( keyValues[ keyPos ] )
    for valPos in range( len( self.dbCatalog[ typeName ][ 'values' ] ) ):
      sqlFields.append( "`%s`" % self.dbCatalog[ typeName ][ 'values' ][ valPos ] )
      sqlValues.append( "(%s*%s)" % ( bucketValues[ valPos ], proportion ) )
    cmd = "INSERT INTO `%s` ( %s ) " % ( self.__getTableName( "bucket", typeName ), ", ".join( sqlFields ) )
    cmd += "VALUES ( %s )" % ", ".join( [ str( val ) for val in sqlValues ] )
    return self._update( cmd, conn = connObj )

  def __checkFieldsExistsInType( self, typeName, fields, tableType ):
    """
    Check wether a list of fields exist for a given typeName
    """
    missing = []
    tableFields = self.dbCatalog[ typeName ][ '%sFields' % tableType ]
    for key in fields:
      if key not in tableFields:
        missing.append( key )
    return missing

  def __checkIncomingFieldsForQuery( self, typeName, selectFields, condDict, groupFields, orderFields, tableType ):
    missing = self.__checkFieldsExistsInType( typeName, selectFields[1], tableType )
    if missing:
      return S_ERROR( "Value keys %s are not defined" % ", ".join( missing ) )
    missing = self.__checkFieldsExistsInType( typeName, condDict, tableType )
    if missing:
      return S_ERROR( "Condition keys %s are not defined" % ", ".join( missing ) )
    missing = self.__checkFieldsExistsInType( typeName, groupFields, tableType )
    if missing:
      return S_ERROR( "Group fields %s are not defined" % ", ".join( missing ) )
    missing = self.__checkFieldsExistsInType( typeName,  orderFields, tableType )
    if missing:
      return S_ERROR( "Order fields %s are not defined" % ", ".join( missing ) )
    return S_OK()


  def retrieveBucketedData( self, typeName, startTime, endTime, selectFields, condDict, groupFields, orderFields, connObj = False ):
    """
    Get data from the DB
      Parameters:
        typeName -> typeName
        startTime & endTime -> int epoch objects. Do I need to explain the meaning?
        selectFields -> tuple containing a string and a list of fields:
                        ( "SUM(%s), %s/%s", ( "field1name", "field2name", "field3name" ) )
        condDict -> conditions for the query
                    key -> name of the field
                    value -> list of possible values
        groupFields -> list of fields to group by
    """
    if typeName not in self.dbCatalog:
      return S_ERROR( "Type %s is not defined" % typeName )
    if len( selectFields ) < 2:
      return S_ERROR( "selectFields has to be a list containing a string and a list of fields" )
    retVal = self.__checkIncomingFieldsForQuery( typeName, selectFields, condDict, groupFields, orderFields, "bucket" )
    if not retVal[ 'OK' ]:
      return retVal
    nowEpoch = Time.toEpoch( Time.dateTime () )
    bucketTimeLength = self.calculateBucketLengthForTime( typeName, nowEpoch , startTime )
    startTime = startTime - startTime % bucketTimeLength
    return self.__queryType( typeName,
                             startTime,
                             endTime,
                             selectFields,
                             condDict,
                             groupFields,
                             orderFields,
                             "bucket" )

  def __queryType( self, typeName, startTime, endTime, selectFields, condDict, groupFields, orderFields, tableType, connObj = False ):
    """
    Execute a query over a main table
    """
    tableName = self.__getTableName( tableType, typeName )
    cmd = "SELECT"
    sqlLinkList = []
    #Calculate fields to retrieve
    realFieldList = []
    for rawFieldName in selectFields[1]:
      keyTable = self.__getTableName( "key", typeName, rawFieldName )
      if rawFieldName in self.dbCatalog[ typeName ][ 'keys' ]:
        realFieldList.append( "`%s`.`value`" % keyTable )
        List.appendUnique( sqlLinkList, "`%s`.`%s` = `%s`.`id`" % ( tableName,
                                                                    rawFieldName,
                                                                    keyTable ) )
      else:
        realFieldList.append( "`%s`.`%s`" % ( tableName, rawFieldName ) )
    try:
      cmd += " %s" % selectFields[0] % tuple( realFieldList )
    except Exception, e:
      return S_ERROR( "Error generating select fields string: %s" % str(e) )
    #Calculate tables needed
    sqlFromList = [ "`%s`" % tableName ]
    for key in self.dbCatalog[ typeName ][ 'keys' ]:
      if key in condDict or key in groupFields or key in selectFields[1]:
        sqlFromList.append( "`%s`" % self.__getTableName( "key", typeName, key ) )
    cmd += " FROM %s" % ", ".join( sqlFromList )
    #Calculate time conditions
    sqlTimeCond = []
    if startTime:
      sqlTimeCond.append( "`%s`.`startTime` >= %s" % ( tableName, startTime ) )
    if endTime:
      if tableType == "bucket":
        endTimeSQLVar = "startTime"
      else:
        endTimeSQLVar = "endTime"
      sqlTimeCond.append( "`%s`.`%s` <= %s" % ( tableName, endTimeSQLVar, endTime ) )
    cmd += " WHERE %s" % " AND ".join( sqlTimeCond )
    #Calculate conditions
    sqlCondList = []
    for keyName in condDict:
      sqlORList = []
      if keyName in self.dbCatalog[ typeName ][ 'keys' ]:
        List.appendUnique( sqlLinkList, "`%s`.`%s` = `%s`.`id`" % ( tableName,
                                                                    keyName,
                                                                    self.__getTableName( "key", typeName, keyName )
                                                                    ) )
      if type( condDict[ keyName ] ) not in ( types.ListType, types.TupleType ):
        condDict[ keyName ] = [ condDict[ keyName ] ]
      for keyValue in condDict[ keyName ]:
        retVal = self._escapeString( keyValue )
        if not retVal[ 'OK' ]:
          return retVal
        keyValue = retVal[ 'Value' ]
        if keyName in self.dbCatalog[ typeName ][ 'keys' ]:
          sqlORList.append( "`%s`.`value` = %s" % ( self.__getTableName( "key", typeName, keyName ), keyValue ) )
        else:
          sqlORList.append( "`%s`.`%s` = %s" % ( tableName, keyName, keyValue ) )
      sqlCondList.append( "( %s )" % " OR ".join( sqlORList ) )
    if sqlCondList:
      cmd += " AND %s" % " AND ".join( sqlCondList )
    #Calculate grouping
    sqlGroupList = []
    if groupFields:
      for field in groupFields:
        if field in self.dbCatalog[ typeName ][ 'keys' ]:
          List.appendUnique( sqlLinkList, "`%s`.`%s` = `%s`.`id`" % ( tableName,
                                                                      field,
                                                                      self.__getTableName( "key", typeName, field )
                                                                    ) )
          sqlGroupList.append( "`%s`.`value`" % self.__getTableName( "key", typeName, field ) )
        else:
          sqlGroupList.append( "`%s`.`%s`" % ( tableName, field ) )
    #Calculate ordering
    sqlOrderList = []
    if orderFields:
      for field in orderFields:
        if field in self.dbCatalog[ typeName ][ 'keys' ]:
          List.appendUnique( sqlLinkList, "`%s`.`%s` = `%s`.`id`" % ( tableName,
                                                                      field,
                                                                      self.__getTableName( "key", typeName, field )
                                                                    ) )
          sqlOrderList.append( "`%s`.`value`" % self.__getTableName( "key", typeName, field ) )
        else:
          sqlOrderList.append( "`%s`.`%s`" % ( tableName, field ) )
    if sqlLinkList:
      cmd += " AND %s" % " AND ".join( sqlLinkList )
    if sqlGroupList:
      cmd += " GROUP BY %s" % ", ".join( sqlGroupList )
    if sqlOrderList:
      cmd += " ORDER BY %s" % ", ".join( sqlOrderList )
    return self._query( cmd, conn = connObj )

  @gSynchro
  def compactBuckets( self ):
    """
    Compact buckets for all defined types
    """
    for typeName in self.dbCatalog:
      self.log.info( "Compacting %s" % typeName )
      self.__compactBucketsForType( typeName )
    return S_OK()

  def __selectForCompactBuckets(self, typeName, timeLimit, bucketLength, nextBucketLength, connObj = False ):
    """
    Nasty SQL query to get ideal buckets using grouping by date calculations and adding value contents
    """
    tableName = self.__getTableName( "bucket", typeName )
    selectSQL = "SELECT "
    sqlSelectList = []
    for field in self.dbCatalog[ typeName ][ 'keys' ]:
      sqlSelectList.append( "`%s`.`%s`" % ( tableName, field ) )
    for field in self.dbCatalog[ typeName ][ 'values' ]:
      sqlSelectList.append( "SUM( `%s`.`%s` )" % ( tableName, field ) )
    sqlSelectList.append( "SUM( `%s`.`entriesInBucket` )" % ( tableName ) )
    sqlSelectList.append( "MIN( `%s`.`startTime` )" % tableName )
    sqlSelectList.append( "MAX( `%s`.`startTime` )" % tableName )
    selectSQL += ", ".join( sqlSelectList )
    selectSQL += " FROM `%s`" % tableName
    selectSQL += " WHERE `%s`.`startTime` < '%s' AND" % ( tableName, timeLimit )
    selectSQL += " `%s`.`bucketLength` = %s" % ( tableName, bucketLength )
    #MAGIC bucketing
    sqlGroupList = [ self.__bucketizeDataField( "`%s`.`startTime`" % tableName, nextBucketLength ) ]
    for field in self.dbCatalog[ typeName ][ 'keys' ]:
      sqlGroupList.append( "`%s`.`%s`" % ( tableName, field ) )
    selectSQL += " GROUP BY %s" % ", ".join( sqlGroupList )
    return self._query( selectSQL, conn = connObj )

  def __deleteForCompactBuckets( self, typeName, timeLimit, bucketLength, connObj = False ):
    """
    Delete compacted buckets
    """
    tableName = self.__getTableName( "bucket", typeName )
    deleteSQL = "DELETE FROM `%s` WHERE " % tableName
    deleteSQL += "`%s`.`startTime` < '%s' AND " % ( tableName, timeLimit )
    deleteSQL += "`%s`.`bucketLength` = %s" % ( tableName, bucketLength )
    return self._update( deleteSQL, conn = connObj )

  def __compactBucketsForType( self, typeName ):
    """
    Compact all buckets for a given type
    """
    tableName = self.__getTableName( "bucket", typeName )
    nowEpoch = Time.toEpoch()
    retVal = self._getConnection()
    if not retVal[ 'OK' ]:
      return retVal
    connObj = retVal[ 'Value' ]
    retVal = self.__startTransaction( connObj )
    if not retVal[ 'OK' ]:
      return retVal
    for bPos in range( len( self.dbBucketsLength[ typeName ] ) - 1 ):
      secondsLimit = self.dbBucketsLength[ typeName ][ bPos ][0]
      bucketLength = self.dbBucketsLength[ typeName ][ bPos ][1]
      timeLimit = ( nowEpoch - nowEpoch % bucketLength ) - secondsLimit
      nextBucketLength = self.dbBucketsLength[ typeName ][ bPos + 1 ][1]
      self.log.verbose( "Compacting data newer that %s with bucket size %s" % ( Time.fromEpoch( timeLimit ), bucketLength ) )
      #Retrieve the data
      retVal = self.__selectForCompactBuckets( typeName, timeLimit, bucketLength, nextBucketLength, connObj )
      if not retVal[ 'OK' ]:
        self.__rollbackTransaction( connObj )
        return retVal
      bucketsData = retVal[ 'Value' ]
      if len( bucketsData ) == 0:
        continue
      retVal = self.__deleteForCompactBuckets( typeName, timeLimit, bucketLength, connObj )
      if not retVal[ 'OK' ]:
        self.__rollbackTransaction( connObj )
        return retVal
      self.log.info( "Compacting %s records %s seconds size for %s" % ( len( bucketsData ), bucketLength, typeName ) )
      #Add data
      for record in bucketsData:
        startTime = record[-2]
        endTime = record[-1]
        valuesList = record[:-2]
        retVal = self.__splitInBuckets( typeName, startTime, endTime, valuesList, connObj )
        if not retVal[ 'OK' ]:
          self.__rollbackTransaction( connObj )
          self.log.error( "Error while compacting data for record in %s: %s" % ( typeName, retVal[ 'Value' ] ) )
    return self.__commitTransaction( connObj )

  def regenerateBuckets( self, typeName ):
    retVal = self._getConnection()
    if not retVal[ 'OK' ]:
      return retVal
    connObj = retVal[ 'Value' ]
    rawTableName = self.__getTableName( "type", typeName )
    retVal = self.__startTransaction( connObj )
    if not retVal[ 'OK' ]:
      return retVal
    self.log.info( "Deleting buckets for %s" % typeName )
    retVal = self._update( "DELETE FROM `%s`" % self.__getTableName( "bucket", typeName ),
                           conn = connObj )
    if not retVal[ 'OK' ]:
      return retVal
    #Generate the common part of the query
    #SELECT fields
    startTimeTableField = "`%s`.startTime" % rawTableName
    endTimeTableField = "`%s`.endTime" % rawTableName
    #Select strings and sum select strings
    sqlSUMSelectList = []
    sqlSelectList = []
    for field in self.dbCatalog[ typeName ][ 'keys' ]:
      sqlSUMSelectList.append( "`%s`.`%s`" % ( rawTableName, field ) )
      sqlSelectList.append( "`%s`.`%s`" % ( rawTableName, field ) )
    for field in self.dbCatalog[ typeName ][ 'values' ]:
      sqlSUMSelectList.append( "SUM( `%s`.`%s` )" % ( rawTableName, field ) )
      sqlSelectList.append( "`%s`.`%s`" % ( rawTableName, field ) )
    sumSelectString = ", ".join( sqlSUMSelectList )
    selectString = ", ".join( sqlSelectList )
    #Grouping fields
    sqlGroupList = []
    for field in self.dbCatalog[ typeName ][ 'keys' ]:
      sqlGroupList.append( "`%s`.`%s`" % ( rawTableName, field ) )
    groupingString = ", ".join( sqlGroupList )
    #List to contain all queries
    sqlQueries = []
    dateInclusiveConditions = []
    countedField = "`%s`.`%s`" % ( rawTableName, self.dbCatalog[ typeName ][ 'keys' ][0] )
    lastTime = Time.toEpoch()
    #Iterate for all ranges
    for iRange in range( len( self.dbBucketsLength[ typeName ] ) ):
      bucketTimeSpan = self.dbBucketsLength[ typeName ][iRange][0]
      bucketLength = self.dbBucketsLength[ typeName ][iRange][1]
      startRangeTime = lastTime - bucketTimeSpan
      endRangeTime = lastTime
      lastTime -= bucketTimeSpan
      bucketizedStart = self.__bucketizeDataField( startTimeTableField, bucketLength )
      bucketizedEnd = self.__bucketizeDataField( endTimeTableField, bucketLength )

      timeSelectString = "MIN(%s), MAX(%s)" % ( startTimeTableField,
                                                endTimeTableField )
      #Is the last bucket?
      if iRange == len( self.dbBucketsLength[ typeName ] ) -1:
        whereString = "%s <= %d" % ( endTimeTableField,
                                     endRangeTime )
      else:
        whereString = "%s > %d AND %s <= %d" % ( startTimeTableField,
                                                  startRangeTime,
                                                  endTimeTableField,
                                                  endRangeTime )
      sameBucketCondition = "(%s) = (%s)" % ( bucketizedStart, bucketizedEnd )
      #Records that fit in a bucket
      sqlQuery = "SELECT %s, %s, COUNT(%s) FROM `%s` WHERE %s AND %s GROUP BY %s, %s" % ( timeSelectString,
                                                                               sumSelectString,
                                                                               countedField,
                                                                               rawTableName,
                                                                               whereString,
                                                                               sameBucketCondition,
                                                                               groupingString,
                                                                               bucketizedStart )
      sqlQueries.append( sqlQuery )
      #Records that fit in more than one bucket
      sqlQuery = "SELECT %s, %s, %s, 1 FROM `%s` WHERE %s AND NOT %s" % ( startTimeTableField,
                                                                          endTimeTableField,
                                                                          selectString,
                                                                          rawTableName,
                                                                          whereString,
                                                                          sameBucketCondition
                                                                        )
      sqlQueries.append( sqlQuery )
      dateInclusiveConditions.append( "( %s )" % whereString )
    #Query for records that are in between two ranges
    sqlQuery = "SELECT %s, %s, %s, 1 FROM `%s` WHERE NOT %s" % ( startTimeTableField,
                                                       endTimeTableField,
                                                       selectString,
                                                       rawTableName,
                                                       " AND NOT ".join( dateInclusiveConditions ) )
    sqlQueries.append( sqlQuery )
    self.log.info( "Retrieving data for rebuilding buckets for type %s..." % ( typeName ) )
    queryNum = 0
    for sqlQuery in sqlQueries:
      self.log.info( "Executing query #%s..." % queryNum )
      queryNum += 1
      retVal = self._query( sqlQuery, conn = connObj )
      if not retVal[ 'OK' ]:
        self.log.error( "Can't retrieve data for rebucketing", retVal[ 'Message' ] )
        self.__rollbackTransaction( connObj )
        return retVal
      rawData = retVal[ 'Value' ]
      self.log.info( "Retrieved %s records" % len( rawData ) )
      for entry in rawData:
        startT = entry[0]
        endT = entry[1]
        values = entry[2:]
        retVal = self.__splitInBuckets( typeName, startT, endT, values, connObj = connObj )
        if not retVal[ 'OK' ]:
          self.__rollbackTransaction( connObj )
          return retVal
    return self.__commitTransaction( connObj )


  def __startTransaction( self, connObj ):
    return self._query( "START TRANSACTION", conn = connObj)

  def __commitTransaction( self, connObj ):
    return self._query( "COMMIT", conn = connObj)

  def __rollbackTransaction( self, connObj ):
    return self._query( "ROLLBACK", conn = connObj)

  def __bucketizeDataField( self, dataField, bucketLength ):
    return "%s - ( %s %% %s )" % ( dataField, dataField, bucketLength )
