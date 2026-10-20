"""Small native Tk file/arrow icons, independent of installed symbol fonts."""
import tkinter as tk


def create(master, *, export=False):
    icon = tk.PhotoImage(master=master, width=20, height=20)

    def line(x0, y0, x1, y1, color):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for n in range(steps + 1):
            icon.put(color, (round(x0 + (x1 - x0) * n / steps), round(y0 + (y1 - y0) * n / steps)))

    ink = '#3769a2'
    for edge in ((3,2,10,2), (10,2,13,5), (13,5,13,8), (3,2,3,17), (3,17,9,17), (10,2,10,5), (10,5,13,5), (6,8,9,8), (6,11,9,11)):
        line(*edge, ink)
    color = '#228064' if export else '#2864dc'
    tip, tail = (9,17) if export else (17,9)
    for x in (13,14): line(x,tail,x,tip,color)
    shoulder = tip + 4 if export else tip - 4
    line(10,shoulder,13,tip,color); line(13,tip,17,shoulder,color)
    return icon
