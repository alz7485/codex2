"""Square pyramid in model space; the camera axes are shared with Blender."""
import math

VERTICES = ((-1,-1,-.54),(1,-1,-.54),(1,1,-.54),(-1,1,-.54),(0,0,1.14))
# First and second plate directions at each station.
RAILS = ((1,4),(2,4),(3,4),(0,4),(3,2))
YAW, TILT = map(math.radians,(22,19))

def camera_space(v):
    x,z,h = v
    depth = x*math.sin(YAW) + z*math.cos(YAW)
    return (x*math.cos(YAW)-z*math.sin(YAW),
            h*math.cos(TILT)-depth*math.sin(TILT),
            depth*math.cos(TILT)+h*math.sin(TILT))

def rail_directions(index):
    origin = camera_space(VERTICES[index])
    directions = []
    for other in RAILS[index]:
        target = camera_space(VERTICES[other])
        length = math.dist(origin,target)
        directions.append(tuple((b-a)/length for a,b in zip(origin,target)))
    return directions

def heading(index):
    a,b = rail_directions(index)
    return math.atan2(-(a[1]+b[1]),a[0]+b[0])
