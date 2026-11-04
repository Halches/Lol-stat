"""Main-page figures and plots from the existing loaded-match snapshot."""
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
import home_model
import render
import ui_skin


def blend(a,b,weight):
    return tuple(round(x*(1-weight)+y*weight) for x,y in zip(render.rgb(a),render.rgb(b)))


def metric_image(snapshot,key,title,detail,width,height,palette,scale):
    image=ui_skin.surface_image(width,height,palette['panel'],palette['line'],
                                palette['gold']).convert('RGBA')
    d=ImageDraw.Draw(image)
    px=lambda n:round(n*scale)
    label_font=render.font('Golos Text',px(13))
    small_font=render.font('Golos Text',max(9,px(10)))
    number_font=render.font('Forum',px(46))
    value=snapshot['stats'][key]
    precision=2 if key in ('kda','vsm') else 1
    text=f'{value:.{precision}f}'.replace('.',',')+('%' if key=='wr' else '') if value is not None else '—'
    d.text((px(13),px(10)),title,font=label_font,fill=palette['mute'])
    render.sculpted_text(image,(px(13),px(27)),text,number_font,palette['fg'])
    if key=='wr' and value is not None:
        size=min(px(68),width//4)
        left=width-size-px(18)
        box=(left,px(34),left+size,px(34)+size)
        d.arc(box,0,360,fill=palette['tag_r'],width=max(2,px(7)))
        d.arc(box,-90,-90+value*3.6,fill=palette['good'],width=max(2,px(7)))
    elif value is not None:
        games=list(reversed(snapshot['selected'][:20]))
        values=[]
        for game in games:
            if key=='kda':
                v=((game['k']+game['a'])/max(1,game['d'])
                   if all(home_model.number(game.get(k)) for k in ('k','d','a')) else None)
            else:
                v=game.get(key)
            values.append(v if home_model.number(v) else None)
        valid=[v for v in values if v is not None]
        if valid:
            low,high=min(valid),max(valid)
            left,right,bottom=px(13),width-px(13),height-px(29)
            top=px(86)
            if bottom>top:
                d.line((left,bottom,right,bottom),fill=palette['line'],width=1)
                tone=palette[{'kda':'gold','csm':'bad','vsm':'good'}[key]]
                run=[]
                def paint(points):
                    if len(points)>1:
                        d.polygon(points+[(points[-1][0],bottom),(points[0][0],bottom)],
                                  fill=blend(palette['panel'],tone,.17))
                        d.line(points,fill=tone,width=max(1,px(2)))
                for i,v in enumerate(values):
                    if v is None:
                        paint(run);run=[];continue
                    x=left+(right-left)*i/max(1,len(values)-1)
                    y=(top+bottom)/2 if high==low else bottom-(bottom-top)*(v-low)/(high-low)
                    run.append((x,y))
                paint(run)
    # Bound the detail to the available card width, including compact windows.
    text=detail
    while small_font.getlength(text)>width-px(26) and len(text)>1:
        text=text[:-2]
    if text!=detail:
        text=text.rstrip()+'…'
    d.text((px(13),height-px(22)),text,font=small_font,fill=palette['mute'])
    return image


class Metric(tk.Canvas):
    def __init__(self,parent,snapshot,key,title,detail,palette,scale):
        super().__init__(parent,bg=palette['panel'],highlightthickness=0,
                         height=round(148*scale),width=1)
        self.snapshot,self.key,self.title,self.detail=snapshot,key,title,detail
        self.palette,self.scale=palette,scale
        self.photo=None;self.signature=None
        self.bind('<Configure>',self.paint)
        self.pack(fill='both',expand=True)

    def paint(self,event):
        signature=(event.width,event.height)
        if event.widget is not self or min(signature)<4 or signature==self.signature:
            return
        image=metric_image(self.snapshot,self.key,self.title,self.detail,*signature,
                           self.palette,self.scale)
        self.photo=ImageTk.PhotoImage(image,master=self)
        self.delete('all');self.create_image(0,0,anchor='nw',image=self.photo)
        self.signature=signature
