#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pywikibot import family
import pywikibot, json, csv, sys

# Log in to the Wikibase instance
site = pywikibot.Site('ldwg', 'ldwg')
site.login()

repo = site.data_repository()

# read in the faculty scrape JSON file
with open('vu-faculty.json', 'rt', encoding='utf-8') as fileObject:
    jsonString = fileObject.read()
data = json.loads(jsonString)

for fac in data:

#fac = data[0]
#if 1==1:
#    print(fac)
    # don't add if name includes "(Deceased)"
    if '(Deceased)' not in fac['name']:
        # remove "(On Leave)" from name
        if '(On Leave)' in fac['name']:
            fac['name'] = fac['name'].replace('(On Leave)','')
        # check for surnames followed by "II", "III", etc. since they don't have commas
        testName = fac['name'].split(' ')
        if testName[1].strip() == "II":
            splitName = fac['name'].split('II')
            name = splitName[1].strip() + ' ' + splitName[0].strip() + ' II'
        elif testName[1].strip() == "III":
            splitName = fac['name'].split('III')
            name = splitName[1].strip() + ' ' + splitName[0].strip() + ' III'
        elif testName[1].strip() == "IV":
            splitName = fac['name'].split('IV')
            name = splitName[1].strip() + ' ' + splitName[0].strip() + ' IV'
        else:
            splitName = fac['name'].split(',')
            name = splitName[1].strip() + ' ' + splitName[0].strip()
        
        some_labels = {"en": name}
        new_item = pywikibot.ItemPage(repo)
        new_item.editLabels(labels=some_labels, summary="Setting labels")

        claim = pywikibot.Claim(repo, u'P4') # employer
        target = pywikibot.ItemPage(repo, u"Q3") # Vanderbilt University
        claim.setTarget(target)
        new_item.addClaim(claim, summary=u'Adding employer claim')
            
        claim = pywikibot.Claim(repo, u'P6') # instance of
        target = pywikibot.ItemPage(repo, u"Q5") # human
        claim.setTarget(target)
        new_item.addClaim(claim, summary=u'Adding type claim')

        #P39 position held
        #P101 field of work
        #P106 occupation
        #P463 member of
        #Looks like we could use P803 (professorship) as the property for the rank.
        #P937 is "work location"
        #P108 is "employer"

        print(new_item.getID(), name)
