xquery version "3.1";
declare namespace rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";

let $records := fn:collection('doi')

(: wrap all of the merged rdf:Description elements inside a single rdf:RDF element :)
return file:write("c:\test\doi\doi-all.rdf",<rdf:RDF>{
    for $description in $records/rdf:RDF/rdf:Description
    return $description
}</rdf:RDF>
)