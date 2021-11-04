(: Note: this takes a really lon time to run because it has to make 17,000+ HTTP calls.  This newer version does a sort of "paging" to break the results into separate RDF/XML files of 1000 records per file :)

declare namespace search="http://www.orcid.org/ns/search";
declare namespace common="http://www.orcid.org/ns/common";
declare namespace http="http://expath.org/ns/http-client";
declare namespace rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#";
declare namespace rdfs = "http://www.w3.org/2000/01/rdf-schema#";
declare namespace prism = "http://prismstandard.org/namespaces/basic/2.1/";
declare namespace bibo = "http://purl.org/ontology/bibo/";

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
let $acceptType := "application/rdf+xml"
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

(: let $textDoi := http:send-request(<http:request method='get' href='https://raw.githubusercontent.com/HeardLibrary/semantic-web/master/2018-spring/vu-people/vanderbilt-doi.csv'/>)[2] :)
let $textDoi := file:read-text('file:///c:/test/vanderbilt-doi.csv')
let $xmlDoi := csv:parse($textDoi, map { 'header' : true(),'separator' : "," })

let $numberOfResults := count($xmlDoi/csv/record)
let $pages := $numberOfResults idiv 1000 (: pages are sets of 1000 results :)
let $remainder := $numberOfResults mod 1000

return (
    for $page in (0 to $pages - 1)
    return 
    file:write("c:\test\doi\doi"||string($page)||".rdf",
          <rdf:RDF>{
          for $record in (1 to 1000)
              let $uri := $xmlDoi/csv/record[$page * 1000 + $record]/work/text()
              return local:generate-description-element($uri)
          }</rdf:RDF>
       )
   ,

    file:write("c:\test\doi\doi"||string($pages)||".rdf",
          <rdf:RDF>{
              for $record in (1 to $remainder)
              let $uri := $xmlDoi/csv/record[$pages * 1000 + $record]/work/text()   
              return local:generate-description-element($uri)
          }</rdf:RDF>
       ) 
)

