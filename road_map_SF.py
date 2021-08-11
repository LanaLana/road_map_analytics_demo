import numpy as np
from geojson import Polygon, Feature, FeatureCollection, dump
import geojson
from shapely import geometry
import rasterio
from rasterio.mask import mask
from rasterio import features
from rasterio.plot import plotting_extent
import cv2
from PIL import Image, ImageEnhance
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import shutil

def download_Landsat_rgb(year='2021', path=44, row=34):
    s3_scenes = pd.read_csv('http://landsat-pds.s3.amazonaws.com/c1/L8/scene_list.gz', compression='gzip')

    scenes = s3_scenes[(s3_scenes.path == path) & (s3_scenes.row == row) & 
                           (s3_scenes.cloudCover <= 5) & 
                           (~s3_scenes.productId.str.contains('_T2')) &
                           (~s3_scenes.productId.str.contains('_RT')) &
                            s3_scenes.acquisitionDate.str.contains(year)]
    print(' Found {} images\n'.format(len(scenes)))

    if len(scenes):
        scene = scenes.sort_values('cloudCover')

    bulk_list = []
    bulk_list.append(scene)
    bulk_frame = pd.concat(bulk_list, 1)

    # Import requests and beautiful soup
    #! pip install bs4
    target_files = ['B4.TIF', 'B3.TIF', 'B2.TIF'] # 432 rgb
    LANDSAT_PATH = './'
    # For each row
    for i, row in bulk_frame.iterrows():

        # Print some the product ID
        print('\n', 'EntityId:', row.productId, '\n')
        print(' Checking content: ', '\n')

        # Request the html text of the download_url from the amazon server. 
        # download_url example: https://landsat-pds.s3.amazonaws.com/c1/L8/139/045/LC08_L1TP_139045_20170304_20170316_01_T1/index.html
        response = requests.get(row.download_url)

        # If the response status code is fine (200)
        if response.status_code == 200:

            # Import the html to beautiful soup
            html = BeautifulSoup(response.content, 'html.parser')

            # Create the dir where we will put this image files.
            entity_dir = os.path.join(LANDSAT_PATH, row.productId)
            os.makedirs(entity_dir, exist_ok=True)

            # Second loop: for each band of this image that we find using the html <li> tag
            for li in html.find_all('li'):

                # Get the href tag
                file = li.find_next('a').get('href')
                if file.split('_')[-1] not in target_files:
                    continue
                print('  Downloading: {}'.format(file))

                # Download the files
                # code from: https://stackoverflow.com/a/18043472/5361345

                response = requests.get(row.download_url.replace('index.html', file), stream=True)

                with open(os.path.join(entity_dir, file), 'wb') as output:
                    shutil.copyfileobj(response.raw, output)
                del response

        break # download just the first one
        
    return row.productId
        
def create_geojson_ext(top = 4189040,
                        bottom = 4172536,
                        left = 541512,
                        right = 558675):
    # set coordinates of the study area

    geos = Polygon([[(right, top), (left, top), (left, bottom), (right,   bottom)]])  

    features = []
    features.append(Feature(geometry=geos, properties={"county": "San Francisco"}))

    feature_collection = FeatureCollection(features, crs={
            "type": "name",
            "properties": {
                "name": "EPSG:32610"
            }
        })

    with open('extention.geojson', 'w') as f:
        dump(feature_collection, f)
        
    print('Create geojson with extention')
        
def crop_resize(input_file, output_file, geojson_file, crs, interpolate=True): 
    
    # create extention
    with open(geojson_file, 'r+', encoding="utf-8") as f:
        gj = geojson.load(f)
    pol = geometry.Polygon(gj['features'][-1]['geometry']['coordinates'][0])
    
    # crop tif image
    with rasterio.open(input_file) as f: 
        chm_crop, chm_crop_affine = mask(f,[pol],crop=True)
        ras_meta = f.profile
    
    chm_extent = plotting_extent(chm_crop[0], chm_crop_affine)
    ras_meta['width'] = chm_crop.shape[1] 
    ras_meta['height'] = chm_crop.shape[2] 
    ras_meta['transform'] = rasterio.Affine(chm_crop_affine[0], 0, chm_crop_affine[2], 0, chm_crop_affine[4],chm_crop_affine[5])
    #print(ras_meta)
    
    if interpolate:
        dim = (chm_crop.shape[1]*3, chm_crop.shape[2]*3) 
        new_crop = chm_crop.transpose(1,2,0)
        chm_crop = np.expand_dims(cv2.resize(new_crop, dim, interpolation=cv2.INTER_NEAREST), 0)
        ras_meta['width'] = chm_crop.shape[1] 
        ras_meta['height'] = chm_crop.shape[2] 
        ras_meta['transform'] = rasterio.Affine(10, 0, chm_crop_affine[2], 0, -10,chm_crop_affine[5])
    
    with rasterio.open(output_file, 'w', **ras_meta) as dst:
        dst.write(chm_crop[0], indexes=1)

def crop_rgb(productId): #row.productId
    target_files = ['B4.TIF', 'B3.TIF', 'B2.TIF']
    
    if 'crop' not in os.listdir('./'):
        os.mkdir('crop')

    for ch in target_files:
        input_file = './{}/{}_{}'.format(productId, productId, ch)
        output_file = './crop/{}'.format(ch)
        crop_resize(input_file=input_file, output_file=output_file, geojson_file='extention.geojson', crs='32610')

def normalize():
    with rasterio.open('./crop/B4.TIF') as src:
        r = src.read(1)
        r = (r - np.min(r)) / (np.max(r) - np.min(r)) * 255
    with rasterio.open('./crop/B3.TIF') as src:
        g = src.read(1)
        g = (g - np.min(g)) / (np.max(g) - np.min(g)) * 255
    with rasterio.open('./crop/B2.TIF') as src:
        b = src.read(1)
        b = (b - np.min(b)) / (np.max(b) - np.min(b)) * 255

    img = Image.fromarray(np.uint8(np.asarray([r, g, b]).transpose(1,2,0)))
    filter = ImageEnhance.Brightness(img)
    new_image = filter.enhance(2)
    filter = ImageEnhance.Contrast(new_image)
    new_image = filter.enhance(2)

    #display(new_image)
    new_image.save('rgb_vis.png')

    with rasterio.open('./crop/B4.TIF') as f: 
        meta_data = f.profile
    meta_data['count'] = 3   
    meta_data['dtype'] = rasterio.uint8     
    with rasterio.open('tci.jpg', 'w', **meta_data) as dst:
        dst.write(np.rollaxis(np.array(new_image), axis=2))
        
    print('Normalize and save true color image')
        
# functions are based on my previous repo https://github.com/LanaLana/forest_height

def write_tif_mask(rst_fn, out_fn, polys, polys_value=None):
    # convert geojson polygons to raster
    
    rst = rasterio.open(rst_fn)
    meta = rst.meta.copy()
    meta.update(compress='lzw')
    meta['dtype'] = rasterio.uint8
    with rasterio.open(out_fn, 'w+', **meta) as out:

        out_arr = out.read(1)

        # this is where we create a generator of geom, value pairs to use in rasterizing
        if polys_value != None:
            shapes = ((geom,value) for geom, value in zip(polys, polys_value))
        else:
            shapes = ((geom,1) for geom in polys)

        burned = features.rasterize(shapes=shapes, fill=0, out=out_arr, transform=out.transform)
        out.write_band(1, burned)
        
def read_geojson(geojson_fn):
    with open(geojson_fn, encoding="utf-8") as src:
        gj = geojson.loads(src.read())

    polys = []
    for ind, feature in enumerate(gj.features):
        if feature['geometry']['type'] == 'MultiPolygon':
            for pol in feature['geometry']['coordinates']:
                if len(pol) == 1:
                    polys.append(Polygon(pol, holes = None)) 
                else:
                    holes = []
                    for hole in pol[1:]:
                        holes.append(hole) 
                    polys.append(Polygon(pol, holes = holes)) 
        else:
            if len(feature['geometry']['coordinates']) == 1:
                    polys.append(Polygon(feature['geometry']['coordinates'][0], holes = None)) 
            else:
                holes = []
                for hole in feature['geometry']['coordinates'][1:]:
                    holes.append(hole) #[0]
                polys.append(Polygon(feature['geometry']['coordinates'][0], holes = holes)) 
    return polys

def convert_road2tif():
    geojson_fn = 'roads_buffered.geojson'
    gj = read_geojson(geojson_fn)

    rst_fn = './crop/B4.TIF' #'out.TIF'
    out_fn = 'roads.tif'

    write_tif_mask(rst_fn, out_fn, gj)
    
    print('Convert road geojson to tif')

def merge_rgb_roads():
    with rasterio.open('./crop/B4.TIF') as src:
        r = src.read(1)
        r = (r - np.min(r)) / (np.max(r) - np.min(r)) * 255
    with rasterio.open('./crop/B3.TIF') as src:
        g = src.read(1)
        g = (g - np.min(g)) / (np.max(g) - np.min(g)) * 255
    with rasterio.open('./crop/B2.TIF') as src:
        b = src.read(1)
        b = (b - np.min(b)) / (np.max(b) - np.min(b)) * 255

    with rasterio.open('roads.tif') as src:
        roads = src.read(1)

    r = np.where(roads == 1, 255, r)
    g = np.where(roads == 1, 69, g)
    b = np.where(roads == 1, 0, b)

    img = Image.fromarray(np.uint8(np.asarray([r, g, b]).transpose(1,2,0)))
    filter = ImageEnhance.Brightness(img)
    new_image = filter.enhance(2)
    filter = ImageEnhance.Contrast(new_image)
    new_image = filter.enhance(2)

    #display(new_image)
    new_image.save('roads_vis.png') 

    with rasterio.open('./crop/B4.TIF') as f: 
        meta_data = f.profile
    meta_data['count'] = 3 
    meta_data['dtype'] = rasterio.uint8       
    with rasterio.open('map.jpg', 'w', **meta_data) as dst:
        dst.write(np.rollaxis(np.array(new_image), axis=2))
        
    print('Merge RGB and map')

def main():
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Input files:
    #              geojson road map:         'roads_buffered.geojson'
    #
    # Output files:
    #              dir with Landsat rgb:     './[productId]/[...]'
    #              dir with crop Landsat:    './crop'
    #              
    #              not georef enchanced rgb: 'rgb_vis.png'
    #              not georef road map:      'roads_vis.png'
    #
    #              geojson study area:       'extention.geojson'
    #              georef norm RGB image:    'tci.jpg'
    #              georef road map:          'map.jpg'
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    print('start')
    productId = download_Landsat_rgb(year='2021', path=44, row=34)
    create_geojson_ext()
    crop_rgb(productId)
    normalize()
    convert_road2tif()
    merge_rgb_roads()
    
if __name__=="__main__":
    main()