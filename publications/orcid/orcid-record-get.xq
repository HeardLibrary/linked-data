declare namespace search="http://www.orcid.org/ns/search";
declare namespace common="http://www.orcid.org/ns/common";

declare function local:query-endpoint($url)
{
(: Accept header can be specified explicitly as below.  Options are "application/json" for JSON and "application/xml" for XML. :)
let $acceptType := "application/xml"
let $request := <http:request href='{$url}' method='get'><http:header name='Accept' value='{$acceptType}'/></http:request>
return
  http:send-request($request)
};


(: For this test, I've used only a single person's ORCID ID.  We'd want to run it for the whole VU set :)
let $endpoint := 'https://orcid.org/0000-0003-3127-2722'
let $response := local:query-endpoint($endpoint)

return $response
