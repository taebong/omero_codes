import re
from numpy import zeros
import numpy as np
import sys

from omero.gateway import BlitzGateway
import omero.util.script_utils as script_utils
import omero.scripts as scripts
import omero
from omero.rtypes import rint, rlong, rstring, robject, unwrap

COLOURS = script_utils.COLOURS

DEFAULT_T_REGEX = "_T"
DEFAULT_Z_REGEX = "_Z"
DEFAULT_C_REGEX = "_C"

channel_regexes = {
    DEFAULT_C_REGEX: r'_C(?P<C>.+?)(_|$)',
    "C": r'C(?P<C>\w+?)',
    "_c": r'_c(?P<C>\w+?)',
    "_w": r'_w(?P<C>\w+?)',
    "Channel": r'Channel(?P<C>.+?)(_|$)',
    "None": False}

z_regexes = {
    DEFAULT_Z_REGEX: r'_Z(?P<Z>\d+)',
    "Z": r'Z(?P<Z>\d+)',
    "_z": r'_z(?P<Z>\d+)',
    "None": False}

time_regexes = {
    DEFAULT_T_REGEX: r'_T(?P<T>\d+)',
    "T": r'T(?P<T>\d+)',
    "_t": r'_t(?P<T>\d+)',
    "Time": r'Time(?P<T>\d+)',
    "None": False}


################ to be changed depending on data
input_dataset_id = 4514  #Dataset ID where individual images are
output_dataset_id = 4516  #Dataset ID where combined images will be stored
session_id = 'd21d9940-ccc9-4d0b-853b-de8192e6f579'    #session id
filter_pattern = 'Well\w{3}_Field\d{1}'

parameter_map = {}
parameter_map["Channel_Name_Pattern"] = 'None'
parameter_map["Time_Name_Pattern"] = 'Time'
parameter_map["Z_Name_Pattern"] = 'None'
parameter_map["Channel_Colours"]=['Green']
##################

client = omero.client("omero.hms.harvard.edu")
session = client.joinSession(session_id)
conn = BlitzGateway(client_obj=client)

#get DataSet
input_dataset = conn.getObject("Dataset",input_dataset_id)   #input dataset
output_dataset = conn.getObject("Dataset",output_dataset_id)

images = list(input_dataset.listChildren())
images.sort(key=lambda x: x.name.lower())
image_ids = [x.getId() for x in images]
image_names = [x.name for x in images]

if parameter_map["Channel_Name_Pattern"] == 'None':
    parameter_map["Channel_Names"] = [ch.getLabel() for ch in images[0].getChannels()]

colour_map = {}
if "Channel_Colours" in parameter_map:
    for c, colour in enumerate(parameter_map["Channel_Colours"]):
        if colour in COLOURS:
            colour_map[c] = COLOURS[colour]

# get the services we need
services = {}
services["containerService"] = session.getContainerService()
services["renderingEngine"] = session.createRenderingEngine()
services["queryService"] = session.getQueryService()
services["pixelsService"] = session.getPixelsService()
services["rawPixelStore"] = conn.c.sf.createRawPixelsStore()
services["rawPixelStoreUpload"] = conn.c.sf.createRawPixelsStore()
services["updateService"] = session.getUpdateService()
services["rawFileStore"] = session.createRawFileStore()


def get_plane(raw_pixel_store, pixels, the_z, the_c, the_t):
    """
    This method downloads the specified plane of the OMERO image and returns
    it as a numpy array.

    @param session      The OMERO session
    @param imageId      The ID of the image to download
    @param pixels       The pixels object, with pixelsType
    @param imageName    The name of the image to write. If no path, saved in
                        the current directory.
    """

    # get the plane
    pixels_id = pixels.getId().getValue()
    raw_pixel_store.setPixelsId(pixels_id, True)
    return script_utils.download_plane(
        raw_pixel_store, pixels, the_z, the_c, the_t)

def get_image_names(query_service, image_ids):
    id_string = ",".join([str(i) for i in image_ids])
    query_string = "select i from Image i where i.id in (%s)" % id_string
    images = query_service.findAllByQuery(query_string, None)
    id_map = {}
    for i in images:
        iid = i.getId().getValue()
        name = i.getName().getValue()
        id_map[iid] = name
    return id_map


def pick_pixel_sizes(pixel_sizes):
    """
    Process a list of pixel sizes and pick sizes to set for new image.
    If we have different sizes from different images, return None
    """
    pix_size = None
    for px in pixel_sizes:
        if px is None:
            continue
        if pix_size is None:
            pix_size = px
        else:
            # compare - if different, return None
            if (pix_size.getValue() != px.getValue() or
                    pix_size.getUnit() != px.getUnit()):
                return None
    return pix_size

def assign_images_by_regex(parameter_map, image_ids, query_service, source_z, source_c, source_t,
                           id_name_map=None):

    c = None
    regex_channel = channel_regexes[parameter_map["Channel_Name_Pattern"]]
    if regex_channel:
        c = re.compile(regex_channel)
    
    t = None
    regex_t = time_regexes[parameter_map["Time_Name_Pattern"]]
    if regex_t:
        t = re.compile(regex_t)

    z = None
    regex_z = z_regexes[parameter_map["Z_Name_Pattern"]]
    if regex_z:
        z = re.compile(regex_z)

    # other parameters we need to determine
    size_z = source_z
    size_c = source_c
    size_t = source_t
    z_start = None      # could be 0 or 1 ?
    t_start = None

    image_map = {}  # map of (z,c,t) : imageId
    
    channels = []

    if id_name_map is None:
        id_name_map = get_image_names(query_service, image_ids)

    # assign each (imageId,zPlane) to combined image (z,c,t) by name.
    for iid in image_ids:
        name = id_name_map[iid]

        if source_t == 1:
            if t:
                t_search = t.search(name)
            if t is None or t_search is None:
                the_t = 0
            else:
                the_t = int(t_search.group('T'))

            size_t = max(size_t, the_t+1)
            if t_start is None:
                t_start = the_t
            else:
                t_start = min(t_start, the_t)
        else:
            t_start = 0
            size_t = source_t
        
        if source_c == 1:
            if c:
                c_search = c.search(name)
            if c is None or c_search is None:
                c_name = "0"
            else:
                c_name = c_search.group('C')
            if c_name in channels:
                the_c = channels.index(c_name)
            else:
                the_c = len(channels)
                channels.append(c_name)
        else:
            channels = parameter_map['Channel_Names']

        if source_z == 1:
            if z:
                z_search = z.search(name)

            if z is None or z_search is None:
                the_z = 0
            else:
                the_z = int(z_search.group('Z'))

            size_z = max(size_z, the_z+1)
            if z_start is None:
                z_start = the_z
            else:
                z_start = min(z_start, the_z)
        else:
            z_start = 0
            size_z = source_z

        for src_z in range(source_z):
            if source_z > 1:
                to_z = src_z
            else:
                to_z = the_z
            
            for src_c in range(source_c):
                if source_c > 1:
                    to_c = src_c
                else:
                    to_c = the_c
                
                for src_t in range(source_t):
                    if source_t > 1:
                        to_t = src_t
                    else:
                        to_t = the_t
                    
                    image_map[(to_z, to_c, to_t)] = (iid, src_z, src_c, src_t)
 
    # if indexes were 1-based (or higher), need to shift indexes accordingly.
    if t_start > 0 or z_start > 0:
        size_t = size_t-t_start
        size_z = size_z-z_start
        i_map = {}
        for key, value in image_map.items():
            z, c, t = key
            i_map[(z-z_start, c, t-t_start)] = value
    else:
        i_map = image_map

    c_names = {}
    for c, name in enumerate(channels):
        c_names[c] = name

    return (size_z, c_names, size_t, i_map)


def make_single_image(services, parameter_map, image_ids, dataset, colour_map):
    """
    This takes the images specified by image_ids, sorts them in to Z,C,T
    dimensions according to parameters in the parameter_map, assembles them
    into a new Image, which is saved in dataset.
    """

    if len(image_ids) == 0:
        return

    rendering_engine = services["renderingEngine"]
    query_service = services["queryService"]
    pixels_service = services["pixelsService"]
    raw_pixel_store = services["rawPixelStore"]
    raw_pixel_store_upload = services["rawPixelStoreUpload"]
    update_service = services["updateService"]
    container_service = services["containerService"]

    # Filter images by name if user has specified filter.
    id_name_map = None
    if "Filter_Names" in parameter_map:
        filter_string = parameter_map["Filter_Names"]
        if len(filter_string) > 0:
            id_name_map = get_image_names(query_service, image_ids)
            image_ids = [i for i in image_ids
                         if id_name_map[i].find(filter_string) > -1]

    image_id = image_ids[0]

    # get pixels, with pixelsType, from the first image
    query_string = "select p from Pixels p join fetch p.image i join "        "fetch p.pixelsType pt where i.id='%d'" % image_id
    pixels = query_service.findByQuery(query_string, None)
    # use the pixels type object we got from the first image.
    pixels_type = pixels.getPixelsType()

    # combined image will have same X and Y sizes...
    size_x = pixels.getSizeX().getValue()
    size_y = pixels.getSizeY().getValue()
    # if we have a Z stack, use this in new image (don't combine Z)
    source_z = pixels.getSizeZ().getValue()
    # if we have multiple channels in source images, use this in new image (don't combine channel)
    source_c = pixels.getSizeC().getValue()
    # if source image is time lapse, use this in new image (don't combine time)
    source_t = pixels.getSizeT().getValue()

    # Now we need to find where our planes are coming from.
    # imageMap is a map of destination:source, defined as (newX, newY,
    # newZ):(imageId, z)
    size_z, c_names, size_t, image_map = assign_images_by_regex(
        parameter_map, image_ids, query_service, source_z, source_c, source_t, id_name_map)

    size_c = len(c_names)

    print size_z, size_c, size_t, source_z, source_c, source_t

    if "Channel_Names" in parameter_map:
        for c, name in enumerate(parameter_map["Channel_Names"]):
            c_names[c] = name

    if "Filter_Names" in parameter_map:
        filter_string = parameter_map["Filter_Names"]
        image_name = filter_string
    else:
        image_name = "combinedImage"
        
    description = "created from image Ids: %s" % image_ids

    channel_list = range(size_c)
    iid = pixels_service.createImage(size_x, size_y, size_z, size_t,
                                     channel_list, pixels_type, image_name,
                                     description)
    image = container_service.getImages("Image", [iid.getValue()], None)[0]

    pixels_id = image.getPrimaryPixels().getId().getValue()
    raw_pixel_store_upload.setPixelsId(pixels_id, True)

    pixel_sizes = {'x': [], 'y': []}
    for the_c in range(size_c):
        min_value = 0
        max_value = 0
        for the_z in range(size_z):
            for the_t in range(size_t):
                if (the_z, the_c, the_t) in image_map:
                    image_id, plane_z, plane_c, plane_t = image_map[(the_z, the_c, the_t)]
                    query_string = "select p from Pixels p join fetch "                        "p.image i join fetch p.pixelsType pt where "                        "i.id='%d'" % image_id
                    pixels = query_service.findByQuery(query_string,
                                                       None)
                    plane_2d = get_plane(raw_pixel_store, pixels, plane_z,
                                         plane_c, plane_t)
                    # Note pixels sizes (may be None)
                    pixel_sizes['x'].append(pixels.getPhysicalSizeX())
                    pixel_sizes['y'].append(pixels.getPhysicalSizeY())
                else:
                    plane_2d = zeros((size_y, size_x))
                
                script_utils.upload_plane_by_row(
                    raw_pixel_store_upload, plane_2d, the_z, the_c, the_t)
                min_value = min(min_value, plane_2d.min())
                max_value = max(max_value, plane_2d.max())
        
        pixels_service.setChannelGlobalMinMax(pixels_id, the_c,
                                              float(min_value),
                                              float(max_value))
        rgba = COLOURS["White"]
        if the_c in colour_map:
            rgba = colour_map[the_c]
        
        script_utils.reset_rendering_settings(rendering_engine, pixels_id,
                                              the_c, min_value, max_value,
                                              rgba)

    # rename new channels
    pixels = rendering_engine.getPixels()
    # has channels loaded - (getting Pixels from image doesn't)
    i = 0

    for c in pixels.iterateChannels():
        # c is an instance of omero.model.ChannelI
        if i >= len(c_names):
            break
        lc = c.getLogicalChannel()  # returns omero.model.LogicalChannelI
        lc.setName(rstring(c_names[i]))
        update_service.saveObject(lc)
        i += 1

    # Set pixel sizes if known
    pix_size_x = pick_pixel_sizes(pixel_sizes['x'])
    pix_size_y = pick_pixel_sizes(pixel_sizes['y'])
    if pix_size_x is not None or pix_size_y is not None:
        # reload to avoid OptimisticLockException
        pixels = services["queryService"].get('Pixels',
                                              pixels.getId().getValue())
        if pix_size_x is not None:
            pixels.setPhysicalSizeX(pix_size_x)
        if pix_size_y is not None:
            pixels.setPhysicalSizeY(pix_size_y)
        services["updateService"].saveObject(pixels)

    # put the image in dataset, if specified.
    if dataset and dataset.canLink():
        link = omero.model.DatasetImageLinkI()
        link.parent = omero.model.DatasetI(dataset.getId(), False)
        link.child = omero.model.ImageI(image.getId().getValue(), False)
        update_service.saveAndReturnObject(link)
    else:
        link = None

    return image, link


def func(filter_name,services=services,parameter_map=parameter_map,
         image_ids=image_ids,output_dataset=output_dataset,colour_map=colour_map):
    parameter_map["Filter_Names"]=filter_name
    make_single_image(services,parameter_map,image_ids,output_dataset,colour_map)
    
if __name__ == "__main__":
    filter_names = np.array([])
    for image_name in image_names:
        try:
            filter_name = re.search(filter_pattern,image_name).group(0)
            filter_names = np.append(filter_names,filter_name)
        except:
            continue
    filter_names = np.unique(filter_names)
    #filter_names = np.unique([re.search(filter_pattern,x).group(0) for x in image_names])    
    for name in filter_names:
        func(name)

 

