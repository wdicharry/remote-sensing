import operator
from osgeo import gdal, gdalnumeric, ogr, osr
from PIL import Image, ImageDraw
import numpy

import os, sys

import subprocess

import logging
logger = logging.getLogger(__name__)

# This function will convert the rasterized clipper shapefile to a
# mask for use within GDAL.    
def imageToArray(i):
    """
    Converts a Python Imaging Library array to a gdalnumeric image.
    """
    a=gdalnumeric.fromstring(i.tostring(),'b')
    a.shape=i.im.size[1], i.im.size[0]
    return a

def arrayToImage(a):
    """
    Converts a gdalnumeric array to a Python Imaging Library Image.
    """
    i=Image.fromstring('L',(a.shape[1],a.shape[0]),
            (a.astype('b')).tostring())
    return i
     
def world2Pixel(geoMatrix, x, y):
  """
  Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
  the pixel location of a geospatial coordinate 
  """
  ulX = geoMatrix[0]
  ulY = geoMatrix[3]
  xDist = geoMatrix[1]
  yDist = geoMatrix[5]
  rtnX = geoMatrix[2]
  rtnY = geoMatrix[4]
  pixel = int((x - ulX) / xDist)
  line = int((ulY - y) / xDist)
  return (pixel, line) 

def histogram(a, bins=range(0,256)):
  """
  Histogram function for multi-dimensional array.
  a = array
  bins = range of numbers to match 
  """
  fa = a.flat
  n = gdalnumeric.searchsorted(gdalnumeric.sort(fa), bins)
  n = gdalnumeric.concatenate([n, [len(fa)]])
  hist = n[1:]-n[:-1] 
  return hist

def stretch(a):
  """
  Performs a histogram stretch on a gdalnumeric array image.
  """
  hist = histogram(a)
  im = arrayToImage(a)   
  lut = []
  for b in range(0, len(hist), 256):
    # step size
    step = reduce(operator.add, hist[b:b+256]) / 255
    # create equalization lookup table
    n = 0
    for i in range(256):
      lut.append(n / step)
      n = n + hist[i+b]
  im = im.point(lut)
  return imageToArray(im)

def clip_raster_good(raster, shp, output):
    # Load the source data as a gdalnumeric array
    srcArray = numpy.asarray([gdalnumeric.LoadFile(raster)])
    
    # Also load as a gdal image to get geotransform (world file) info
    srcImage = gdal.Open(raster)
    geoTrans = srcImage.GetGeoTransform()
    
    # Create an OGR layer from a Field boundary shapefile
    field = ogr.Open("%s.shp" % shp)
    lyr = field.GetLayer(shp)
    poly = lyr.GetNextFeature()
    
    # Convert the layer extent to image pixel coordinates
    minX, maxX, minY, maxY = lyr.GetExtent()
    ulX, ulY = world2Pixel(geoTrans, minX, maxY)
    lrX, lrY = world2Pixel(geoTrans, maxX, minY)
    
    # Calculate the pixel size of the new image
    pxWidth = int(lrX - ulX)
    pxHeight = int(lrY - ulY)
    
    clip = srcArray[:, ulY:lrY, ulX:lrX]
    
    # Create a new geomatrix for the image
    geoTrans = list(geoTrans)
    geoTrans[0] = minX
    geoTrans[3] = maxY
    
    # Map points to pixels for drawing the field boundary on a blank
    # 8-bit, black and white, mask image.
    points = []
    pixels = []
    geom = poly.GetGeometryRef()
    pts = geom.GetGeometryRef(0)
    for p in range(pts.GetPointCount()):
      points.append((pts.GetX(p), pts.GetY(p)))
    for p in points:
      pixels.append(world2Pixel(geoTrans, p[0], p[1]))
    rasterPoly = Image.new("L", (pxWidth, pxHeight), 1)
    rasterize = ImageDraw.Draw(rasterPoly)
    rasterize.polygon(pixels, 0)
    mask = imageToArray(rasterPoly)   
    
    # Clip the image using the mask
    clip = gdalnumeric.choose(mask, (clip, 0)).astype(gdalnumeric.uint8)
    
    # This image has 3 bands so we stretch each one to make them
    # visually brighter
    #for i in range(3):
    #  clip[i,:,:] = stretch(clip[i,:,:])
    
    # Save ndvi as tiff
    gdalnumeric.SaveArray(clip, "%s.tif" % output, format="GTiff", prototype=raster)
    
    # Save ndvi as an 8-bit jpeg for an easy, quick preview
    clip = clip.astype(gdalnumeric.uint8)
    gdalnumeric.SaveArray(clip, "%s.jpg" % output, format="JPEG")

def clip_raster_hack(raster, shp, output):
    #shapefile = '%s.shp' % shp
    args = [
        'gdalwarp',
        '-cutline',
        shp,
        '-crop_to_cutline',
        '-overwrite',
        raster,
        output + '.tif']
    logger.debug('Calling "%s"', ' '.join(args))
    subprocess.call(' '.join(args), shell=True, stdout = sys.stdout, stderr = sys.stderr)

def clip_raster(raster,shp, output):
    logger.debug("Masking %s using %s to %s", raster, shp, output)
    clip_raster_hack(raster,shp, output)

def main():
    if len(sys.argv) < 4:
        print "Usage: %s <raster-file> <shapefile> <output>" % sys.argv[0]
        sys.exit(-1)
        
    clip_raster(sys.argv[1], sys.argv[2], sys.argv[3])
    
if __name__ == '__main__':
    main()
    

