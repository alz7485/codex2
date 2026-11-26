"""Composite cropped blur without changing the global rasterization or layer order."""
import math
from PIL import ImageFilter

def over(out,layer):
    box=layer.getbbox()  # alpha only is safe for unfiltered source
    if box is not None:out.alpha_composite(layer.crop(box),box[:2])

def blur_over(out,layer,radius):
    if layer.width*layer.height<65536:
        out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius)));return
    # Pillow blur operates on straight RGBA, so include nonzero RGB even at alpha=0.
    box=layer.getbbox(alpha_only=False)
    if box is None:return
    pad=math.ceil(6*radius)+8
    l,t,r,b=box;box=(max(0,l-pad),max(0,t-pad),min(layer.width,r+pad),min(layer.height,b+pad))
    if (box[2]-box[0])*(box[3]-box[1])>=layer.width*layer.height*.8:
        out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius)));return
    out.alpha_composite(layer.crop(box).filter(ImageFilter.GaussianBlur(radius)),box[:2])
