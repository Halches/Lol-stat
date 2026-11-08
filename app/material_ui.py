"""Static, composited Tk materials. Existing controls and commands stay native.

Frames and text share the same pixels, so glass gradients are not covered by
opaque rectangular label backgrounds. No timer, animation or screen capture.
"""
import math
import tkinter as tk
from tkinter import font as tkfont
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import render
import material_assets
from scroll_canvas import ScrollCanvas


def mix(a,b,t):
    a=render.rgb(a) if isinstance(a,str) else a
    b=render.rgb(b) if isinstance(b,str) else b
    return tuple(round(x*(1-t)+y*t) for x,y in zip(a,b))


@lru_cache(maxsize=3)
def atmosphere(width,height,bg,accent,dark,scale=1):
    """Quiet, static coloured mist. Generated once per size, never animated."""
    if dark and bg=='#180f22':
        artwork=material_assets.backdrop(width,height,scale)
        if artwork is not None:return artwork
    w,h=256,160
    base=render.rgb(bg);light=render.rgb(accent)
    image=Image.new('RGB',(w,h));pixels=image.load()
    for y in range(h):
        for x in range(w):
            nx,ny=x/w,y/h
            # Unequal clouds leave the reading area dark; the light belongs to
            # the distant background, not to every panel independently.
            wave=(math.sin(nx*18+ny*8)+math.sin(nx*31-ny*15)*.45+math.sin(nx*51+ny*27)*.18)/1.63
            pink=(.34*math.exp(-(((nx-.75)/.20)**2+((ny-.075)/.09)**2))+
                  .43*math.exp(-(((nx-.06)/.09)**2+((ny-.68)/.23)**2))+
                  .16*math.exp(-(((nx-.84)/.16)**2+((ny-.94)/.19)**2)))
            violet=.27*math.exp(-(((nx-.43)/.15)**2+((ny-.14)/.13)**2))
            pink*=.62+.38*wave;violet*=.76-.24*wave
            pink+=.13*math.exp(-((ny-(.18-.13*nx+.025*math.sin(nx*14)))/.045)**2)*math.exp(-((nx-.72)/.40)**2)
            if not dark:pink*=.18;violet*=.15
            pink_colour=mix(light,'#b04da8',.57) if dark else light
            colour=mix(base,pink_colour,min(.75,pink*1.38))
            colour=mix(colour,mix(light,'#6350b4',.78) if dark else light,violet)
            pixels[x,y]=colour
    return image.resize((max(1,width),max(1,height)),Image.Resampling.BICUBIC)


@lru_cache(maxsize=32)
def reflected_light(width,height,accent,role):
    """Broad coloured reflections baked into a reusable static texture."""
    w,h=128,48;image=Image.new('RGBA',(w,h));pixels=image.load()
    for y in range(h):
        for x in range(w):
            nx,ny=x/(w-1),y/(h-1)
            left=.37*math.exp(-(((nx-.08)/.21)**2+((ny+.18)/.85)**2))
            centre=.22*math.exp(-(((nx-.64)/.24)**2+((ny+.20)/.75)**2))
            streak=.40*math.exp(-((nx-.92+.18*(ny-.5))/.095)**2-((ny-.40)/.9)**2)
            amount=(left+centre+streak)*(1 if role=='panel' else .72)
            colour=mix(mix(accent,'#8c6aa6',.40),mix(accent,'#d58bbf',.40),nx)
            pixels[x,y]=colour+(round(170*amount),)
    return image.resize((width,height),Image.Resampling.BICUBIC)


def glass(background,fill,accent,active=False,rail=False,role='panel'):
    """Composite tinted glass, a soft external shadow and antialiased bevels.

    The source background stays visible through the face. Padding reserves the
    shadow inside the image so child widgets cannot clip it at the outer edge.
    """
    width,height=background.size
    if min(width,height)<4:return background.copy()
    if rail or role=='sidebar':
        result=Image.blend(background.convert('RGB'),Image.new('RGB',(width,height),fill),.35)
        overlay=Image.new('RGBA',(width,height));d=ImageDraw.Draw(overlay)
        d.line((width-1,0,width-1,height),fill=render.rgb(accent)+(72,))
        d.line((width-2,0,width-2,height),fill=(0,0,0,90))
        result=result.convert('RGBA');result.alpha_composite(overlay)
        return result.convert('RGB')
    if accent=='#d5addb' and fill in ('#35253f','#21152d','#654572') and role!='inset':
        artwork=material_assets.panel(width,height,active,role in ('button','pill'))
        if artwork is not None:
            result=background.convert('RGBA');result.alpha_composite(artwork)
            return result.convert('RGB')
    compact=role in ('button','pill','inset')
    inset=role=='inset'
    pad=1 if compact else 2 if role=='row' else 3
    bottom=2 if compact else 3 if role=='row' else 6
    radius=min(11,max(4,height//3))
    box=(pad,pad,width-pad-1,height-bottom-1)
    if box[3]<=box[1]:return background.copy()
    ss=3
    def mask_for(coords,offset=0):
        mask=Image.new('L',(width*ss,height*ss));d=ImageDraw.Draw(mask)
        d.rounded_rectangle(tuple(round(v*ss) for v in coords),radius=radius*ss,fill=255)
        return mask.resize((width,height),Image.Resampling.LANCZOS)
    mask=mask_for(box)
    result=background.convert('RGBA')
    if not compact:
        shadow_mask=mask_for((pad,4,width-pad-1,height-2)).filter(ImageFilter.GaussianBlur(3))
        shadow=Image.new('RGBA',(width,height),(4,2,10,0));shadow.putalpha(shadow_mask.point(lambda a:round(a*.38)))
        result.alpha_composite(shadow)
    # A translucent body and broad reflections, not an opaque vertical gradient.
    face=Image.new('RGBA',(width,height));d=ImageDraw.Draw(face)
    dark=sum(render.rgb(fill))<450
    for y in range(height):
        t=y/max(1,height-1)
        highlight=(.60 if active else .30)*(1-t)**2
        if inset:highlight=.04+.05*t
        colour=mix(fill,accent,highlight+(0.12 if role=='button' and not active else .03 if not compact else 0))
        colour=mix(colour,'#0c0817' if dark else '#ffffff',.13*t)
        opacity=(210 if active else 155 if compact else 145) if dark else 185
        d.line((0,y,width,y),fill=colour+(opacity,))
    result.alpha_composite(Image.composite(face,Image.new('RGBA',(width,height)),mask))
    if not compact and dark:
        veil=reflected_light(width,height,accent,role)
        result.alpha_composite(Image.composite(veil,Image.new('RGBA',(width,height)),mask))
    elif active:
        veil=reflected_light(width,height,accent,'panel')
        result.alpha_composite(Image.composite(veil,Image.new('RGBA',(width,height)),mask))
    bevel=Image.new('RGBA',(width*ss,height*ss));d=ImageDraw.Draw(bevel)
    coords=tuple(v*ss for v in box)
    edge=mix(fill,accent,.58 if active else .43)
    d.rounded_rectangle(coords,radius=radius*ss,outline=edge+(135,),width=ss)
    top=mix(accent,'#ffffff',.42)
    # Thin specular upper rim and darker inner lower edge are independently lit.
    y=(pad+1)*ss
    d.line(((pad+radius)*ss,y,(width-pad-radius-1)*ss,y),fill=top+(135 if active else 80,),width=ss)
    d.line(((pad+radius)*ss,(height-bottom-2)*ss,(width-pad-radius-1)*ss,(height-bottom-2)*ss),fill=(5,3,12,95),width=ss)
    if active:
        d.rounded_rectangle(tuple((v+1 if i<2 else v-1)*ss for i,v in enumerate(box)),radius=(radius-1)*ss,outline=render.rgb(accent)+(60,),width=ss)
    result.alpha_composite(bevel.resize((width,height),Image.Resampling.LANCZOS))
    return result.convert('RGB')


def manager(widget):
    try:
        return getattr(widget.winfo_toplevel(),'_material',None)
    except (tk.TclError,AttributeError):return None


def sample(widget,width,height):
    """Crop a parent material in local coordinates; labels never draw flat patches."""
    mgr=manager(widget)
    if not mgr:return Image.new('RGB',(max(1,width),max(1,height)),widget.cget('bg'))
    x,y=widget.winfo_x(),widget.winfo_y();parent=widget.master
    while parent is not None:
        image=getattr(parent,'_material_pixels',None)
        if image is not None and image.width>1 and getattr(parent,'_material_layer',False):
            # Crop safely when a child extends beyond a clipped viewport.
            out=Image.new('RGB',(max(1,width),max(1,height)),mgr.palette['bg'])
            out.paste(image,(-x,-y));return out
        if parent is mgr.root:break
        x+=parent.winfo_x();y+=parent.winfo_y();parent=parent.master
    root=mgr.root
    rw,rh=max(1,root.winfo_width()),max(1,root.winfo_height())
    image=atmosphere(rw,rh,mgr.palette['bg'],mgr.palette['gold'],mgr.palette['dark'],mgr.scale)
    out=Image.new('RGB',(max(1,width),max(1,height)),mgr.palette['bg']);out.paste(image,(-x,-y));return out


class Manager:
    def __init__(self,root,palette,scale=1):
        previous=getattr(root,'_material',None)
        if previous:previous.close()
        self.root,self.palette=root,dict(palette)
        self.scale=scale
        root._material=self
        self.active=None
        self.dirty={};self.job=None
        self.resize_job=None;self.root_size=None
        old=getattr(root,'_material_resize_binding',None)
        if old:
            try:root.unbind('<Configure>',old)
            except tk.TclError:pass
        root._material_resize_binding=root.bind('<Configure>',self.root_resized,add='+')
        root._material_destroy_binding=root.bind('<Destroy>',lambda e:self.close() if e.widget is root else None,add='+')

    def close(self):
        for job in (self.job,self.resize_job):
            if job:
                try:self.root.after_cancel(job)
                except tk.TclError:pass
        self.job=self.resize_job=None;self.dirty.clear()
        for event,name in (('<Configure>','_material_resize_binding'),('<Destroy>','_material_destroy_binding')):
            binding=getattr(self.root,name,None)
            if binding:
                try:self.root.unbind(event,binding)
                except tk.TclError:pass
                setattr(self.root,name,None)

    def root_resized(self,event):
        if event.widget is not self.root:return
        size=(event.width,event.height)
        if size==self.root_size:return
        self.root_size=size
        if self.resize_job:self.root.after_cancel(self.resize_job)
        self.resize_job=self.root.after(100,self.refresh_background)

    def refresh_background(self):
        self.resize_job=None
        # Header/status can move without changing their own size. Refresh the
        # visible background after the root size settles, not on each scroll.
        for child in self.root.winfo_children():
            if isinstance(child,Frame):self.queue(child,True)
        if self.active is not None and self.active.winfo_exists():self.queue(self.active,True)

    def queue(self,widget,force=False):
        self.dirty[widget]=self.dirty.get(widget,False) or force
        if self.job is None:self.job=self.root.after_idle(self.flush)

    def flush(self):
        seen=set()
        while self.dirty:
            pending=self.dirty;self.dirty={}
            for widget,force in sorted(pending.items(),key=lambda item:item[0]._w.count('.')):
                force=force or self.dirty.pop(widget,False)
                if widget in seen or not widget.winfo_exists():continue
                seen.add(widget)
                widget._material_paint_now(force=force)
        self.job=None

    def activate(self,page):
        if self.active is page:return
        if self.active is not None and self.active.winfo_exists():self.release(self.active)
        self.active=page

    def release(self,widget):
        for child in widget.winfo_children():self.release(child)
        if isinstance(widget,Frame):
            widget._material_art.configure(image='')
            widget._material_photo=None;widget._material_pixels=None;widget._material_signature=None
        elif isinstance(widget,Label):
            widget.delete('all');widget._photo=None;widget._material_signature=None
        elif isinstance(widget,Viewport):
            widget.itemconfigure(widget._background,image='')
            widget._viewport_photo=None;widget._material_signature=None
        elif isinstance(widget,tk.Canvas) and hasattr(widget,'photo') and not getattr(widget,'_material_keep_image',False):
            widget.delete('all');widget.photo=None
            if hasattr(widget,'signature'):widget.signature=None


class Frame(tk.Frame):
    def __init__(self,parent,**kwargs):
        self.material_role=kwargs.pop('material_role',None)
        super().__init__(parent,**kwargs)
        self._material_pixels=None;self._material_signature=None;self._material_photo=None
        self._material_art=tk.Label(self,bd=0,highlightthickness=0,takefocus=0,bg=self.cget('bg'))
        self._material_art.place(x=0,y=0,relwidth=1,relheight=1,bordermode='outside')
        # Forward pointer events only. Forwarding Destroy would invoke page
        # cleanup handlers while rebuilding an unrelated background label.
        for sequence in ('<Button-1>','<Enter>','<Leave>'):
            self._material_art.bind(sequence,lambda e,s=sequence:self.event_generate(s,x=e.x,y=e.y))
        self.bind('<Configure>',self._material_paint,add='+')
        self.bind('<Map>',lambda e:self._material_paint(force=True),add='+')

    def bind(self,sequence=None,func=None,add=None):
        # Screen-specific resize handlers must coexist with the material layer.
        if sequence=='<Configure>' and func is not None:add='+'
        return super().bind(sequence,func,add)

    def configure(self,cnf=None,**kwargs):
        result=super().configure(cnf,**kwargs)
        changes=dict(cnf) if isinstance(cnf,dict) else {}
        changes.update(kwargs)
        if hasattr(self,'_material_art') and any(k in changes for k in ('bg','background')):
            self._material_paint(force=True)
        return result
    config=configure

    def winfo_children(self):
        # A background is part of the frame, not an application content widget.
        # Page refreshes may freely destroy/rebuild their ordinary children.
        art=getattr(self,'_material_art',None)
        return [child for child in super().winfo_children() if child is not art]

    def _material_image(self,width,height):
        image=sample(self,width,height);mgr=manager(self)
        if not mgr:return image
        bg=self.cget('bg');parentbg=self.master.cget('bg') if 'background' in self.master.keys() else mgr.palette['bg']
        isolated=bool(self.material_role) or (bg!=parentbg and bg in (mgr.palette['panel'],mgr.palette['deep'],mgr.palette['raise']))
        self._material_layer=isolated
        if bg not in (mgr.palette['bg'],mgr.palette['panel'],mgr.palette['deep'],mgr.palette['raise']):
            self._material_layer=True
            return Image.new('RGB',(width,height),bg)
        if isolated:
            return glass(image,bg,mgr.palette['gold'],active=bg==mgr.palette['raise'],role=self.material_role or 'panel')
        return image

    def _material_paint(self,event=None,force=False):
        mgr=manager(self)
        if mgr:mgr.queue(self,force)
        else:self._material_paint_now(force=force)

    def _material_paint_now(self,force=False):
        if not self.winfo_exists() or not self.winfo_ismapped():return
        width,height=self.winfo_width(),self.winfo_height()
        if min(width,height)<4:return
        # Scrolling moves the static material with its content. Position-only
        # Configure events must not regenerate a page full of images.
        signature=(width,height,self.cget('bg'))
        if signature==self._material_signature and not force:return
        self._material_signature=signature
        self._material_pixels=self._material_image(width,height)
        self._material_photo=ImageTk.PhotoImage(self._material_pixels,master=self)
        self._material_art.configure(image=self._material_photo)
        self._material_art.lower()
        if not getattr(self,'_material_layer',False):
            # Plain containers don't serve as a sampling source. Keep the Tk
            # image only, rather than a second full-size RGB copy of the page.
            self._material_pixels=None
        # Parent images arrive before the next layout idle, after child Configure.
        for child in self.winfo_children():
            if isinstance(child,(Frame,Label,Viewport)):
                child._material_paint(force=True)


class Viewport(ScrollCanvas):
    """Static background for uncovered scroll space, excluded from scroll bounds."""
    def __init__(self,parent,**kwargs):
        super().__init__(parent,**kwargs)
        self._background=self.create_image(0,0,anchor='nw')
        self._viewport_photo=None;self._material_signature=None
        self.bind('<Configure>',self._material_paint,add='+')
        self.bind('<Map>',lambda e:self._material_paint(force=True),add='+')

    def bbox(self,*args):
        if args==('all',):
            if self._content_window is None:return None
            box=super().bbox(self._content_window)
            return (box[0],box[1]+self._offset,box[2],box[3]+self._offset) if box else None
        return super().bbox(*args)

    def _material_paint(self,event=None,force=False):
        mgr=manager(self)
        if mgr:mgr.queue(self,force)

    def _material_paint_now(self,force=False):
        if not self.winfo_exists() or not self.winfo_ismapped():return
        size=(self.winfo_width(),self.winfo_height())
        if min(size)<2 or (size==self._material_signature and not force):return
        self._material_signature=size
        self._viewport_photo=ImageTk.PhotoImage(sample(self,*size),master=self)
        self.itemconfigure(self._background,image=self._viewport_photo)
        self.tag_lower(self._background)
        for child in self.winfo_children():
            if isinstance(child,(Frame,Label)):child._material_paint(force=True)


class Label(tk.Canvas):
    """Label-compatible canvas, preserving icon assets, bindings and text variables."""
    def __init__(self,parent,**kwargs):
        self.options=dict(text='',image='',compound='none',font=('Golos Text',11),
            bg=parent.cget('bg'),fg='#f3e6f2',anchor='center',justify='center',
            padx=1,pady=1,width=0,height=0,wraplength=0,state='normal',textvariable='')
        self.options.update(kwargs)
        self._material_pixels=None;self._photo=None;self._material_signature=None
        self._variable=None;self._trace=None
        super().__init__(parent,bg=self.options['bg'],bd=0,highlightthickness=0,
                         takefocus=kwargs.get('takefocus',0),cursor=kwargs.get('cursor',''))
        self.bind('<Configure>',self._material_paint,add='+')
        self.bind('<Map>',lambda e:self._material_paint(force=True),add='+')
        self.bind('<Destroy>',self._cleanup,add='+')
        self._set_variable();self._measure()

    def _cleanup(self,event):
        if event.widget is self and self._variable is not None and self._trace:
            try:self._variable.trace_remove('write',self._trace)
            except tk.TclError:pass

    def _set_variable(self):
        var=self.options.get('textvariable')
        if var:
            self._variable=var if isinstance(var,tk.Variable) else tk.StringVar(self,name=str(var))
            self._trace=self._variable.trace_add('write',lambda *_:self.configure(text=self._variable.get()))
            self.options['text']=self._variable.get()

    def cget(self,key):
        key={'background':'bg','foreground':'fg','borderwidth':'bd'}.get(key,key)
        if key in self.options:return self.options[key]
        return super().cget(key)

    def configure(self,cnf=None,**kwargs):
        if cnf:kwargs.update(cnf)
        if not kwargs:return self.options
        kwargs={ {'background':'bg','foreground':'fg'}.get(k,k):v for k,v in kwargs.items() }
        self.options.update(kwargs)
        native={k:v for k,v in kwargs.items() if k in ('cursor','takefocus')}
        if native:super().configure(**native)
        if any(k in kwargs for k in ('text','font','image','width','height','wraplength','padx','pady','compound')):self._measure()
        self._material_paint(force=True)
    config=configure

    def _measure(self):
        o=self.options
        self.delete('measure')
        f=tkfont.Font(root=self,font=o['font'])
        item=self.create_text(0,0,text=str(o['text']),font=o['font'],width=int(o.get('wraplength') or 0),anchor='nw',justify=o['justify'],tags='measure')
        box=self.bbox(item) or (0,0,0,f.metrics('linespace'))
        self.tw,self.th=box[2]-box[0],box[3]-box[1]
        self.delete(item)
        self.iw=self.ih=0
        if o['image']:
            try:self.iw=int(self.tk.call('image','width',o['image']));self.ih=int(self.tk.call('image','height',o['image']))
            except tk.TclError:pass
        mode=o['compound'];gap=5 if self.iw and o['text'] else 0
        self.cw=self.iw+self.tw+gap if mode in ('left','right') else max(self.iw,self.tw)
        self.ch=self.ih+self.th+gap if mode in ('top','bottom') else max(self.ih,self.th)
        if self.iw and mode=='none':self.cw,self.ch=self.iw,self.ih
        width=int(o.get('width') or 0);height=int(o.get('height') or 0)
        if width:self.cw=width if self.iw else width*f.measure('0')
        if height:self.ch=height if self.iw else height*f.metrics('linespace')
        super().configure(width=max(1,self.cw+2*int(o['padx'])),height=max(1,self.ch+2*int(o['pady'])))
        self._material_signature=None

    def _material_paint(self,event=None,force=False):
        mgr=manager(self)
        if mgr:mgr.queue(self,force)
        else:self._material_paint_now(force=force)

    def _material_paint_now(self,force=False):
        if not self.winfo_exists() or not self.winfo_ismapped():return
        width,height=self.winfo_width(),self.winfo_height()
        if min(width,height)<2:return
        o=self.options
        signature=(width,height,str(o),self.winfo_x(),self.winfo_y())
        if signature==self._material_signature and not force:return
        self._material_signature=signature
        image=sample(self,width,height);mgr=manager(self)
        # Pills and selected navigation are intentionally a separate glass layer.
        bg=o['bg'];parentbg=self.master.cget('bg')
        if mgr and bg!=parentbg and bg not in (mgr.palette['bg'],mgr.palette['panel'],mgr.palette['deep']):
            image=glass(image,bg,mgr.palette['gold'],active=bg==mgr.palette['raise'],role='pill')
        self._photo=ImageTk.PhotoImage(image,master=self)
        self.delete('all');self.create_image(0,0,image=self._photo,anchor='nw')
        anchor=o['anchor'];px,py=int(o['padx']),int(o['pady'])
        x=px if anchor in ('w','nw','sw') else width-px-self.cw if anchor in ('e','ne','se') else (width-self.cw)/2
        y=py if anchor in ('n','nw','ne') else height-py-self.ch if anchor in ('s','sw','se') else (height-self.ch)/2
        mode=o['compound'];gap=5 if self.iw and o['text'] else 0
        tx,ty=x,y+(self.ch-self.th)/2;ix,iy=x,y+(self.ch-self.ih)/2
        if mode=='left':tx=x+self.iw+gap
        elif mode=='right':ix=x+self.tw+gap
        elif mode=='top':tx=x+(self.cw-self.tw)/2;ty=y+self.ih+gap;ix=x+(self.cw-self.iw)/2;iy=y
        elif mode=='bottom':tx=x+(self.cw-self.tw)/2;ty=y;ix=x+(self.cw-self.iw)/2;iy=y+self.th+gap
        else:tx=x+(self.cw-self.tw)/2;ix=x+(self.cw-self.iw)/2
        if self.iw:self.create_image(ix,iy,image=o['image'],anchor='nw')
        if o['text'] and (mode!='none' or not self.iw):
            # Native font rasterisation, full opacity, normal keyboard/mouse bindings.
            self.create_text(tx,ty,text=str(o['text']),font=o['font'],fill=o['fg'],
                width=int(o.get('wraplength') or 0),anchor='nw',justify=o['justify'])


class Toggle(Label):
    """Native Tk variables and callbacks with a quiet glass checkbox/radio face."""
    def __init__(self,parent,radio=False,**kwargs):
        self.toggle_var=kwargs.pop('variable',None) or tk.BooleanVar(parent,value=False)
        self.command=kwargs.pop('command',None);self.radio=radio
        self.value=kwargs.pop('value',True);self.onvalue=kwargs.pop('onvalue',True);self.offvalue=kwargs.pop('offvalue',False)
        kwargs.pop('style',None)
        palette=manager(parent).palette
        kwargs.setdefault('fg',palette['fg']);kwargs.setdefault('font',('Golos Text',11))
        kwargs.update(compound='left',anchor='w',takefocus=1,pady=4,cursor='hand2')
        self._indicator=None
        super().__init__(parent,**kwargs)
        self._toggle_trace=self.toggle_var.trace_add('write',lambda *_:self.sync())
        self.bind('<ButtonRelease-1>',lambda e:self.invoke());self.bind('<space>',lambda e:self.invoke())
        self.bind('<Return>',lambda e:self.invoke())
        self.bind('<FocusIn>',lambda e:self._material_paint(force=True));self.bind('<FocusOut>',lambda e:self._material_paint(force=True))
        self.bind('<Destroy>',self._toggle_cleanup,add='+');self.sync()

    def _toggle_cleanup(self,event):
        if event.widget is self:
            try:self.toggle_var.trace_remove('write',self._toggle_trace)
            except tk.TclError:pass

    def sync(self):
        if not self.winfo_exists():return
        palette=manager(self).palette
        selected=self.toggle_var.get()==(self.value if self.radio else self.onvalue)
        image=Image.new('RGBA',(24,20));d=ImageDraw.Draw(image)
        box=(1,2,18,19)
        if self.radio:d.ellipse(box,fill=palette['deep'],outline=palette['line'],width=1)
        else:d.rounded_rectangle(box,radius=5,fill=palette['deep'],outline=palette['line'],width=1)
        if selected:
            if self.radio:d.ellipse((6,7,13,14),fill=palette['gold'])
            else:
                d.rounded_rectangle(box,radius=5,fill=palette['raise'],outline=palette['gold'])
                d.line((5,10,9,14,15,7),fill=palette['fg'],width=2)
        self._indicator=ImageTk.PhotoImage(image,master=self)
        self.configure(image=self._indicator)

    def invoke(self):
        if self.options.get('state')=='disabled':return
        self.toggle_var.set(self.value if self.radio else self.offvalue if self.toggle_var.get()==self.onvalue else self.onvalue)
        if self.command:return self.command()
