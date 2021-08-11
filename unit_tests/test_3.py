import sys
sys.path.insert(0, '../')
from road_map_SF import download_Landsat_rgb

def main():
    productId = download_Landsat_rgb(year='2021', path=45, row=33)
    print('Download Landsat image for Santa Rosa')
    
if __name__=="__main__":
    main()