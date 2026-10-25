"""Native 20px cube/plane glyphs; no dependency on symbol fonts."""
import tkinter as tk


def create(master, plane='立体'):
    image=tk.PhotoImage(master=master,width=20,height=20)
    def line(a,b,color):
        x,y=a;u,v=b;n=max(abs(u-x),abs(v-y),1)
        for i in range(n+1):image.put(color,(round(x+(u-x)*i/n),round(y+(v-y)*i/n)))
    def polygon(points,color):
        for y in range(20):
            for x in range(20):
                inside=False
                for a,b in zip(points,points[1:]+points[:1]):
                    if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
                if inside:image.put(color,(x,y))
        for a,b in zip(points,points[1:]+points[:1]):line(a,b,'#42638c')
    if plane=='立体':
        polygon([(2,6),(10,2),(18,6),(10,10)],'#d2e6ff')
        polygon([(2,6),(10,10),(10,18),(2,14)],'#4288e8')
        polygon([(10,10),(18,6),(18,14),(10,18)],'#58c4df')
    else:
        vertices={'XY':[(2,10),(10,5),(18,10),(10,15)],'XZ':[(3,3),(16,3),(16,16),(3,16)],'YZ':[(6,2),(16,6),(16,18),(6,14)]}[plane]
        polygon(vertices,'#d9eaff')
        a=vertices[-1];line(a,vertices[-2],'#d65e54' if plane!='YZ' else '#2b996d')
        line(a,vertices[0],'#2b996d' if plane=='XY' else '#377cdd')
    return image
