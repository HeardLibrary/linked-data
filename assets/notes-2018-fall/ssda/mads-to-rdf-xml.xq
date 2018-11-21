xquery version "3.1";

declare namespace m = "http://www.loc.gov/mods/v3";
declare namespace rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";
declare namespace rdfs = "http://www.w3.org/2000/01/rdf-schema#";
declare namespace dc = "http://purl.org/dc/elements/1.1/";
declare namespace dcterms = "http://purl.org/dc/terms/";
declare namespace geo = "http://www.w3.org/2003/01/geo/wgs84_pos#";
declare namespace dwc = "http://rs.tdwg.org/dwc/terms/";
declare namespace ex = "http://example.org/";

let $dbDoc := file:read-text( 'file:///c:/test/databases.csv')
let $dbXml := csv:parse($dbDoc, map { 'header' : true(),'separator' : "," })
let $databases := $dbXml/csv/record

let $uriDoc := file:read-text( 'file:///c:/test/uri-matches.csv')
let $uriXml := csv:parse($uriDoc, map { 'header' : true(),'separator' : "," })
let $uriMatches := $uriXml/csv/record

let $fileLocation := "c:/test/output/essss.rdf"

return
(:(file:write($fileLocation,:)
<rdf:RDF
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
xmlns:dcterms="http://purl.org/dc/terms/"
xmlns:dc="http://purl.org/dc/elements/1.1/"
xmlns:dwc="http://rs.tdwg.org/dwc/terms/"
xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#"
xmlns:ex="http://example.org/"
>{
  
for $database in $databases
let $records := fn:collection($database/dbName/text())/m:mods
let $domain := "https://slavesocieties.org/"
let $eap := $database/eap/text()
let $archive := $database/archive/text()
let $archiveAbbrev := $database/archiveAbbrev/text()
let $essssIdState := $database/matchEssssId/text()

return 
  for $record at $tempPos in $records
    let $pos :=
        if ($archiveAbbrev="nudl")
        then $tempPos + 14
        else $tempPos
    let $recNum :=
      (: get the record number from the position in the folder (assuming sequential numbering :)
      if (string-length(string($pos))=1)
      then "00"||string($pos)
      else
          if (string-length(string($pos))=2)
          then "0"||string($pos)
          else string($pos)

  let $identifier :=
    if ($essssIdState = "embedded") 
    then (: these are the sites in the "hasIdentifiers" folder whose records contain the essss: ids in their metadata :)
        if ($record/m:identifier/text()  != "")
            then 
              $domain||"essss/"||tokenize($record/m:identifier/text(),":")[2]
            else $domain||"essss/bad/"||string($pos)
    else (: these sites don't have essss: ids embedded in their metadata :)
        if ($essssIdState = "no")
        then  (: no essss: identifier has yet been assigned to records from this site :)
             $domain||$eap||"/"||$archiveAbbrev||"/"||$recNum
        else (: these records have essss: identifiers that need to be looked up in the uri-matches table :)
            let $match :=
                for $uriMatch in $uriMatches
                where $uriMatch/badURI/text() = $domain||$eap||"/"||$archiveAbbrev||"/"||$recNum
                return $uriMatch/goodURI/text()
            return
            (: check for the case where the URI isn't found in the lookup table :)
            if (count($match)=1)
            then  $match  (: a single match was found, so use it as the identifier :)
            else  $domain||$eap||"/"||$archiveAbbrev||"/bad/"||$recNum  (: no match, create a "bad" identifier :)
            
            
  let $geo := $record/m:subject/m:cartographics/m:coordinates/text()
  let $lat := tokenize($geo,",")[1]  
  let $long := tokenize($geo,",")[2]  
  return
    <rdf:Description rdf:about = "{$identifier}">{
         if ($essssIdState !="embedded")
         then (
             <ex:eap>{$eap}</ex:eap>,
             <ex:archive>{$archive}</ex:archive>,
             <ex:number>{$recNum}</ex:number>
           )
         else
           (),
         <rdf:type rdf:resource="http://xmlns.com/foaf/0.1/Document" />,
         
         if ($record/m:titleInfo/m:title/text()  != "")         
         then <dcterms:title>{$record/m:titleInfo/m:title/text()}</dcterms:title>
         else (),
         
         for $name in $record/name
         return
               if ($name/m:role/m:roleTerm/text()="Project Director")
               then <ex:projectDirector>{$name/m:namePart/text()}</ex:projectDirector>
               else   
                   if ($name/m:role/m:roleTerm/text()="project")
                   then <ex:project>{$name/m:namePart/text()}</ex:project>
                   else   
                       if ($name/m:role/m:roleTerm/text()="Metadata Creation")
                       then <ex:metadataCreator>{$name/m:namePart/text()}</ex:metadataCreator>
                       else (),
               
         <dc:format>{$record/m:typeOfResource/text()}</dc:format>,
         <ex:originIssuance>{$record/m:originInfo/m:issuance/text()}</ex:originIssuance>,

         if ($record/m:originInfo/m:languageTerm/text()  != "")
             then <dc:language>{$record/language/m:languageTerm/text()}</dc:language>
             else(),

         if ($record/m:originInfo/m:publisher/text()  != "")
             then <dc:publisher>{$record/m:originInfo/m:publisher/text()}</dc:publisher>
             else (),
         
         if ($record/m:abstract/text()  != "")
             then <dcterms:abstract>{$record/m:abstract/text()}</dcterms:abstract>
             else (),
         
         if ($record/m:identifier/text()  != "")
             then <dcterms:identifier>{$record/m:identifier/text()}</dcterms:identifier>
             else (),
         
         if ($record/m:physicalDescription/m:form/text()  != "")
             then <dcterms:description>{$record/m:physicalDescription/m:form/text()}</dcterms:description>
             else (),
         
         if ($record/m:subject/m:topic/text()  != "")
             then <dc:type>{$record/m:subject/m:topic/text()}</dc:type>
             else (),
         
         if ($record/m:physicalDescription/m:extent/text()  != "")
             then <dcterms:extent>{$record/m:physicalDescription/m:extent/text()}</dcterms:extent>
             else (),
         
         <dc:subject>{$record/m:subject/m:geographic/text()}</dc:subject>,
         <dcterms:temporal>{$record/m:subject/m:temporal/text()}</dcterms:temporal>,
         <dwc:continent>{$record/m:subject/m:hierarchicalGeographic/m:continent/text()}</dwc:continent>,
         <dwc:country>{$record/m:subject/m:hierarchicalGeographic/m:country/text()}</dwc:country>,
         <dwc:stateProvince>{$record/m:subject/m:hierarchicalGeographic/m:province/text()}</dwc:stateProvince>,
         <dwc:municipality>{$record/m:subject/m:hierarchicalGeographic/m:city/text()}</dwc:municipality>,

         if ($lat = "Unknown" or $lat = "")
         then ()
         else <geo:lat>{$lat}</geo:lat>,
         
         if ($long  != "")
         then <geo:long>{$long}</geo:long>
         else (),
         
         if ($record/m:note/text()  != "")
         then <dc:rights>{$record/m:note/text()}</dc:rights>
         else ()

    }</rdf:Description>

}</rdf:RDF>

(:)):)