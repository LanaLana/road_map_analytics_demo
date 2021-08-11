import sys
sys.path.insert(0, '../')
from road_map_SF import download_Landsat_rgb

def main():
    productId = download_Landsat_rgb(year='2020', path=44, row=34)
    print('Download Landsat image for 2020')
    
if __name__=="__main__":
    main()