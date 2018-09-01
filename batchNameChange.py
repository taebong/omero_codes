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
channel_regex = r'_Channel(?P<Channel>.+?)_'
z_regex = False
time_regex = r'Time(?P<Time>\d+?)_'
field_regex = r'\(series (?P<Field>\d+?)\)'
well_regex = r'Well(?P<Well>\w+?)_'

chan_change = {'Fluo Green':'488nm'}

input_dataset_id = 4556 #Dataset ID where individual images are
session_id = '8383bb8e-3e54-459f-b9eb-1614487de6a0'    #session id
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

