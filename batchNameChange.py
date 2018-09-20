# copyright: Tae Yeon Yoo, taeyeon_yoo@hms.harvard.edu

import re
from numpy import zeros
import numpy as np
import sys

from omero.gateway import BlitzGateway
import omero.util.script_utils as script_utils
import omero.scripts as scripts
import omero.clients
import omero
from omero.rtypes import rint, rlong, rstring, robject, unwrap


################ to be changed depending on data
channel_regex = r'_w\d(?P<Channel>.+?).TIF'
z_regex = False
time_regex = r'_t(?P<Time>\d+?)_'
field_regex = r'_Scan_(?P<Field>\w+?)_'
well_regex = r'Well_(?P<Well>\w+?)_'

chan_change = {'Fluo Green':'488nm','Fluo Red':'560nm','Brightfield':'Brightfield'}

input_dataset_id = 4702 #Dataset ID where individual images are
session_id = 'ec4720e6-1e54-44c5-9490-b5804c1f772f'    #session id
##################

regexes = {'Well':well_regex,'Field':field_regex,'Channel':channel_regex,'Z':z_regex,'Time':time_regex}


client = omero.client("omero.hms.harvard.edu")
session = client.joinSession(session_id)
conn = BlitzGateway(client_obj=client)

#get DataSet
input_dataset = conn.getObject("Dataset",input_dataset_id)   #input dataset

images = list(input_dataset.listChildren())
images.sort(key=lambda x: x.name.lower())
image_ids = [x.getId() for x in images]
image_names = [x.name for x in images]

recomps = {}
for key,regex in regexes.items():
    if regex:
        recomps[key] = re.compile(regex)


dim_order = ['Well','Field','Channel','Z','Time']

dims = [dim for dim in dim_order if dim in recomps.keys() ]

new_names = np.array([])

for image_name in image_names:
    new_name = ''
    
    for i,dim in enumerate(dims):
        try:
            match = recomps[dim].search(image_name).group(dim)
        except:
            continue
            
        if (dim == 'Channel'):
            if match in chan_change.keys():
                match = chan_change[match]
                
        new_name = new_name + dim + match
        
        if i < len(dims)-1:
            new_name = new_name + '_'
            
    new_names = np.append(new_names,new_name)

for i,im in enumerate(images):
    im.setName(new_names[i])
    im.save()

