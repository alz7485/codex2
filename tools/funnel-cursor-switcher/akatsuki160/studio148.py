"""Procedural linear-light studio environment; no external texture dependencies."""
import numpy as np
from runtime_render import vtk
from runtime_render import numpy_to_vtk

def setup(r):
    h,w=128,256
    y,x=np.mgrid[0:h,0:w];u=x/w;v=y/h
    env=np.zeros((h,w,3),np.float32);env[:]=[.12,.11,.085]
    for cx,cy,sx,sy,rgb in [(.02,.50,.12,.28,(1.9,1.8,1.5)),(.50,.50,.11,.23,(1.8,1.7,1.5)),(.19,.69,.09,.19,(1.8,2.0,2.3)),(.66,.57,.028,.28,(2.3,2.45,2.7)),(.88,.35,.10,.12,(.85,.72,.51)),(.43,.82,.12,.055,(1.3,1.45,1.7)),(.35,.43,.035,.24,(1.6,1.7,1.9))]:
        du=np.minimum(abs(u-cx),1-abs(u-cx));power=np.exp(-((du/sx)**6+((v-cy)/sy)**6));env+=power[:,:,None]*np.array(rgb,np.float32)
    im=vtk.vtkImageData();im.SetDimensions(w,h,1);im.GetPointData().SetScalars(numpy_to_vtk(np.round(255*np.clip(env/1.15,0,1)**(1/2.2)).astype(np.uint8).reshape(-1,3),deep=True));tex=vtk.vtkTexture();tex.SetInputData(im);tex.InterpolateOn();tex.MipmapOn();r.SetEnvironmentTexture(tex,True);r.UseImageBasedLightingOn();return tex

def material(p,mat):
    c=np.asarray(mat.baseColorFactor)[:3]/255.
    p.SetColor(*c);p.SetInterpolationToPBR();p.SetMetallic(float(mat.metallicFactor));p.SetRoughness(float(mat.roughnessFactor));p.SetAmbient(1);p.SetDiffuse(1)
