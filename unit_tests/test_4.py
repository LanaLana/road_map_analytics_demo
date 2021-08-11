import sys
sys.path.insert(0, '../')
from road_map_SF import create_geojson_ext, download_Landsat_rgb

def main():
    create_geojson_ext(top = 4239576,
                        bottom = 4230796,
                        left = 526200,
                        right = 538706)
    print('Create geojson extention for Santa Rosa. Save in ./unit_test')
    
if __name__=="__main__":
    main()