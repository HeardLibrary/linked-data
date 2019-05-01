xquery version "3.1";

declare namespace adhoc = "https://rawgit.com/HeardLibrary/semantic-web/master/adhoc#";
declare namespace common = "http://www.orcid.org/ns/common";
declare namespace record = "http://www.orcid.org/ns/record";
declare namespace person = "http://www.orcid.org/ns/person";
declare namespace personal-details = "http://www.orcid.org/ns/personal-details";
declare namespace other-name = "http://www.orcid.org/ns/other-name";
declare namespace activities = "http://www.orcid.org/ns/activities";
declare namespace education = "http://www.orcid.org/ns/education";
declare namespace employment = "http://www.orcid.org/ns/employment";
declare namespace work = "http://www.orcid.org/ns/work";
declare namespace rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";
declare namespace rdfs = "http://www.w3.org/2000/01/rdf-schema#";
declare namespace foaf = "http://xmlns.com/foaf/0.1/";
declare namespace schema = "http://schema.org/";
declare namespace dcterms = "http://purl.org/dc/terms/";

declare function local:generate-date($institution as xs:string, $orgType as xs:string, $tag1 as xs:string, $tag2 as xs:string, $dateData as node()*) as node()*
{
for $org in $dateData

(: can't figure out how to just insert the correct organization type into the xpath :)
let $type := 
    if ($orgType = "employment:organization")
    then $org/employment:organization/common:disambiguated-organization/common:disambiguated-organization-identifier/text()
    else $org/education:organization/common:disambiguated-organization/common:disambiguated-organization-identifier/text()
    
where $type = $institution
return (
   element {$tag1} {local:construct-date($org/common:start-date/common:year/text(),$org/common:start-date/common:month/text(),$org/common:start-date/common:day/text() )},
   element {$tag2} {local:construct-date($org/common:end-date/common:year/text(),$org/common:end-date/common:month/text(),$org/common:end-date/common:day/text() )}
     )
};

(: can't figure out how to designate type for the variables without an error when empty sequence :)
declare function local:construct-date($year, $month, $day)
{
  if ($year)
  then if ($month)
       then if ($day)
            then $year||"-"||$month||"-"||$day
            else $year||"-"||$month
       else $year
  else ()
};

declare function local:generate-works-links($works)
{
for $work in $works
   let $ids := $work/common:external-ids/common:external-id
       for $id in $ids
       where $id/common:external-id-type/text() = "doi"
       let $doi := $id/common:external-id-value/text()
       let $cleanDoi := local:clean-doi($doi)
       return element foaf:made {attribute rdf:resource{"http://dx.doi.org/"||$cleanDoi} }
};

declare function local:clean-doi($doi)
{
  let $a := replace(replace($doi,"\}",""),"\{","")  (: get rid of extraneous curly brackets :)
  (: get rid of inappropriate URI forms :)
  let $b := replace($a,"https://doi.org/","")
  let $c := replace($b,"https://dx.doi.org/","")
  let $d := replace($c,"http://dx.doi.org/","")
  let $e := replace($d,"doi: ","")
  let $f := replace($e,"doi:","")
  let $g := replace($f,"DOI: ","")
  let $h := replace($g,"DOI ","")
  return $h
};

let $records := fn:collection('orcid')/record:record
let $organizationID := "5718" (: Vanderbilt's RINGGOLD identifier :)

return (file:write("c:\test\orcid\people.rdf",<rdf:RDF>{
    for $record in $records
    let $orcidURI := $record/common:orcid-identifier/common:uri/text()
    let $orcidID := $record/common:orcid-identifier/common:path/text()
    let $givenName := $record/person:person/person:name/personal-details:given-names/text()
    let $surname := $record/person:person/person:name/personal-details:family-name/text()
    let $altNames := $record/person:person/other-name:other-names/other-name:other-name
    let $works := $record/activities:activities-summary/activities:works/activities:group
    let $student := $record/activities:activities-summary/activities:educations/education:education-summary/education:organization/common:disambiguated-organization/common:disambiguated-organization-identifier/text()
    let $edDate := $record/activities:activities-summary/activities:educations/education:education-summary
    let $job := $record/activities:activities-summary/activities:employments/employment:employment-summary/employment:organization/common:disambiguated-organization/common:disambiguated-organization-identifier/text()
    let $jobDate := $record/activities:activities-summary/activities:employments/employment:employment-summary
    where ($job = $organizationID or $student = $organizationID)
      return 
           element rdf:Description { 
                   attribute rdf:about {$orcidURI},
                   <rdf:type rdf:resource="http://xmlns.com/foaf/0.1/Person" />,
                   <rdf:type rdf:resource="http://schema.org/Person" />,
                   <dcterms:identifier>{$orcidID}</dcterms:identifier>,
                   <adhoc:identifierSource>orcid</adhoc:identifierSource>,
                   <foaf:familyName>{$surname}</foaf:familyName>,
                   <foaf:givenName>{$givenName}</foaf:givenName>,
                   <schema:familyName>{$surname}</schema:familyName>,
                   <schema:givenName>{$givenName}</schema:givenName>,
                   <foaf:name>{$givenName||" "||$surname}</foaf:name>,
                   <rdfs:label>{$givenName||" "||$surname}</rdfs:label>,
                   for $altName in $altNames
                       let $otherName := $altName/other-name:content/text()
                       return <foaf:name>{$otherName}</foaf:name>,
                       
                   local:generate-works-links($works),
                   if ($student  = $organizationID)
                       then (
                       <adhoc:status>student</adhoc:status>,
                       local:generate-date($organizationID, "education:organization", "adhoc:studentStart", "adhoc:studentEnd", $edDate)
                         )
                       else (),
                   if ($job  = $organizationID)
                       then (
                       <adhoc:status>employee</adhoc:status>,
                       local:generate-date($organizationID, "employment:organization", "adhoc:employeeStart", "adhoc:employeeEnd", $jobDate)
                         )
                       else ()
                   }
}</rdf:RDF>
))