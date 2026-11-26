"""Sparse Gaussian compositing; retain global raster and disjoint tile interiors."""
import math
from PIL import ImageFilter
from .fx_local204 import blur_over as original_blur
TILE=192

def blur_over(out,layer,radius):
    if layer.width*layer.height<65536 or radius>24:
        return original_blur(out,layer,radius)
    box=layer.getbbox(alpha_only=False)
    if box is None:return
    pad=math.ceil(6*radius)+8
    l,t,r,b=box
    l,t,r,b=max(0,l-pad),max(0,t-pad),min(layer.width,r+pad),min(layer.height,b+pad)
    if (r-l)*(b-t)<TILE*TILE*4:
        return original_blur(out,layer,radius)
    tiles=[]; occupied=0
    for y in range(t,b,TILE):
        for x in range(l,r,TILE):
            x1,y1=min(r,x+TILE),min(b,y+TILE)
            crop=(max(0,x-pad),max(0,y-pad),min(layer.width,x1+pad),min(layer.height,y1+pad))
            sub=layer.crop(crop)
            if sub.getbbox(alpha_only=False) is None:continue
            tiles.append((x,y,x1,y1,crop));occupied+=sub.width*sub.height
    if occupied >= (r-l)*(b-t)*.85:
        return original_blur(out,layer,radius)
    for x,y,x1,y1,crop in tiles:
        sub=layer.crop(crop).filter(ImageFilter.GaussianBlur(radius))
        out.alpha_composite(sub.crop((x-crop[0],y-crop[1],x1-crop[0],y1-crop[1])),(x,y))
