import json

with open('csv-metadata.json', 'rt', encoding='utf-8') as fileObject:
    text = fileObject.read()
metadata = json.loads(text)

tables = metadata['tables']
for table in tables:
    print(table['url'])
    # assume each table has an aboutUrl and each table is about an entity
    # extract the column name of the subject resource from the URI template
    temp = table['aboutUrl'].partition('{')[2]
    subjectWikidataIdName = temp.partition('}')[0]
    columns = table['tableSchema']['columns']

    # find the column whose name matches the URI template for the aboutUrl (only one)
    for column in columns:
        if column['name'] == subjectWikidataIdName:
            subjectWikidataIdColumnHeader = column['titles']
    print('Subject column: ', subjectWikidataIdColumnHeader)
    
    # find columns without suppressed output (should have properties)
    for column in columns:
        if not('suppressOutput' in column):
            
            # find the columns (if any) that provide labels
            if column['propertyUrl'] == 'rdfs:label':
                labelColumnHeader = column['titles']
                labelLanguage = column['lang']
                print('Label column: ', labelColumnHeader, ', language: ', labelLanguage)
                
            # find columns that contain alternate labels
            elif column['propertyUrl'] == 'skos:altLabel':
                altLabelColumnHeader = column['titles']
                altLabelLanguage = column['lang']
                print('Alternate label column: ', altLabelColumnHeader, ', language: ', altLabelLanguage)
            
            # find columns that contain properties with entity values
            elif 'valueUrl' in column:
                propColumnHeader = column['titles']
                propertyId = column['propertyUrl'].partition('prop/direct/')[2]
                print('Property column: ', propColumnHeader, ', Property ID: ', propertyId)
            
            # remaining columns should have properties with literal values
            else:
                propColumnHeader = column['titles']
                propertyId = column['propertyUrl'].partition('prop/direct/')[2]
                valueDatatype = column['datatype']
                print('Property column: ', propColumnHeader, ', Property ID: ', propertyId, ' Value datatype: ', valueDatatype)

    print()