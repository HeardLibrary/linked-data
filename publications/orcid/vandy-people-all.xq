(: Note: loop to retrieve all records is commented out.  As is, will retrieve only one record for testing purposes. :)

declare namespace search="http://www.orcid.org/ns/search";
declare namespace common="http://www.orcid.org/ns/common";

declare function local:query-endpoint($url)
{
(: Accept header can be specified explicitly as below.  Options are "application/json" for JSON and "application/xml" for XML. :)
let $acceptType := "application/xml"
let $request := <http:request href='{$url}' method='get'><http:header name='Accept' value='{$acceptType}'/></http:request>
return
  http:send-request($request)[2]  (: return only the data and not the HTTP response :)
};

let $endpoint := 'https://orcid.org/'

(:
let $textOrcid := http:send-request(<http:request method='get' href='https://raw.githubusercontent.com/HeardLibrary/semantic-web/master/2018-spring/vu-people/vanderbilt-orcid.csv'/>)[2]
let $xmlOrcid := csv:parse($textOrcid, map { 'header' : true(),'separator' : "|" })

for $orcidRecord in $xmlOrcid/csv/record
let $orcidID := $orcidRecord/orcidId/text()

return $orcidID
:)

let $orcidID := '0000-0003-3127-2722'
let $URI := $endpoint||$orcidID

let $response := local:query-endpoint($URI)

return (file:write("c:\test\orcid\"||$orcidID||".xml",$response),$orcidID)