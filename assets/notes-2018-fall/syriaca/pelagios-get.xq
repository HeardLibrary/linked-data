(: Note: this takes a really lon time to run because it has to make 17,000+ HTTP calls.  This newer version does a sort of "paging" to break the results into separate RDF/XML files of 1000 records per file :)

declare namespace http="http://expath.org/ns/http-client";
declare namespace rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#";
declare namespace rdfs = "http://www.w3.org/2000/01/rdf-schema#";
declare namespace dc = "http://purl.org/dc/elements/1.1/";
declare namespace dcterms = "http://purl.org/dc/terms/";
declare namespace dwc = "http://rs.tdwg.org/dwc/terms/";
declare namespace prism = "http://prismstandard.org/namespaces/basic/2.1/";
declare namespace bibo = "http://purl.org/ontology/bibo/";
declare namespace functx = "http://www.functx.com";
declare namespace skos = "http://www.w3.org/2004/02/skos/core#";
declare namespace geo = "http://www.w3.org/2003/01/geo/wgs84_pos#";
declare namespace lawd = "http://lawd.info/ontology/";
declare namespace example = "http://example.org/";

(: the initial response to dereferencing the DOI is a 303 redirect that returns the actual URL :)
declare function local:get-redirect($uri as xs:string) as xs:string
{
let $response := local:query-endpoint($uri)
return if (string($response[1]/@status)="303")
       then $response[2]/html/body/a/text()
       else "error"
};

declare function local:query-endpoint($endpoint as xs:string)
{
let $acceptType := "application/json"
let $request := <http:request href='{$endpoint}' method='get'><http:header name='Accept' value='{$acceptType}'/></http:request>
return http:send-request($request)
};

declare function local:generate-description-element($uri as xs:string)
{
let $redirectUri := local:get-redirect($uri)
return if ($redirectUri = "error")
       then element rdf:Description { 
                     attribute rdf:about {$uri},
                     <prism:doi>{substring-after($uri,"http://dx.doi.org/")}</prism:doi>,
                     <bibo:doi>{substring-after($uri,"http://dx.doi.org/")}</bibo:doi>,
                     <rdfs:comment>bad doi</rdfs:comment>
                     }
       else local:query-endpoint($redirectUri)[2]/rdf:RDF/rdf:Description
};

let $textPleiadesUris := file:read-text('file:///c:/temp/syriaca-pleiades.csv')
let $xmlPleiadesUris := csv:parse($textPleiadesUris, map { 'header' : true(),'separator' : "," })

let $numberOfResults := count($xmlPleiadesUris/csv/record)

return (

    file:write("c:\test\syriaca-pleiades.rdf", (: to test without the file write, comment out this line and the last line :)

    for $record in (1 to $numberOfResults) (: to test with a single record, replace $numberOfResults with 1 :)
    let $uri := $xmlPleiadesUris/csv/record[$record]/pleiades_place/text()
    (:let $uri := 'http://pleiades.stoa.org/places/893976':)
    let $syriacaId := $xmlPleiadesUris/csv/record[$record]/syriaca_place/text()
    let $fullUri := 'http://peripleo.pelagios.org/peripleo/places/'||web:encode-url($uri)
    let $results := local:query-endpoint($fullUri)[2]

    return
<rdf:RDF 
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
xmlns:dc="http://purl.org/dc/elements/1.1/"
xmlns:dcterms="http://purl.org/dc/terms/"
xmlns:dwc="http://rs.tdwg.org/dwc/terms/"
xmlns:skos="http://www.w3.org/2004/02/skos/core#"
xmlns:lawd="http://lawd.info/ontology/"
xmlns:example="http://example.org/"
>
    <rdf:Description rdf:about = "{$syriacaId}">{
      <rdf:type rdf:resource = "http://lawd.info/ontology/Place"/>,
      <dcterms:source rdf:resource = "{$uri}" />,
      <dcterms:description>{$results/json/description/text()}</dcterms:description>,
      <dcterms:title>{$results/json/title/text()}</dcterms:title>,
      <rdfs:label>{$results/json/title/text()}</rdfs:label>,
      for $name in $results/json/names/_
      return <lawd:hasName>{$name/text()}</lawd:hasName>,
      <rdfs:comment>{$results/json/geometry/type/text()}</rdfs:comment>,
      <geo:long>{$results/json/geometry/coordinates/_[1]/text()}</geo:long>,
      <geo:lat>{$results/json/geometry/coordinates/_[2]/text()}</geo:lat>,
      for $match in $results/json/network/nodes/_
      return <skos:closeMatch>{
                  <rdf:Description rdf:about = "{$match/uri/text()}">{
                    if ($match/label/text()!='')
                    then <rdfs:label>{$match/label/text()}</rdfs:label>
                    else ()
                  }</rdf:Description> 
             }</skos:closeMatch>,
      for $ref in $results/json/referenced__in/_
      return <dcterms:isReferencedBy>{
                  <rdf:Description rdf:about = "{$ref/peripleo__url/text()}">{
                    <rdfs:label>{$ref/title/text()}</rdfs:label>,
                    <dcterms:title>{$ref/title/text()}</dcterms:title>,
                    <dcterms:identifier>{$ref/identifier/text()}</dcterms:identifier>,
                    <example:count>{$ref/count/text()}</example:count>
                  }</rdf:Description> 
             }</dcterms:isReferencedBy>
    }</rdf:Description> 
</rdf:RDF>
       )
)

