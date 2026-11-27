"""Static dimensional surfaces and controls shared by the desktop screens."""
import math
import tkinter as tk
from tkinter import ttk, font as tkfont
from functools import lru_cache
from PIL import Image, ImageDraw, ImageTk
import render
import material_ui


def heading_color(palette):
    return '#dcc0b4' if palette['bg']=='#180f22' and palette['gold']=='#d5addb' else palette['gold']


@lru_cache(maxsize=24)
def surface_image(width,height,fill,edge,accent,raised=False):
    return material_ui.glass(Image.new('RGB',(max(4,width),max(4,height)),fill),fill,accent,active=raised)


def Frame(parent,**kwargs):
    return material_ui.Frame(parent,**kwargs) if material_ui.manager(parent) else tk.Frame(parent,**kwargs)


def Label(parent,**kwargs):
    return material_ui.Label(parent,**kwargs) if material_ui.manager(parent) else tk.Label(parent,**kwargs)


def TtkLabel(parent,**kwargs):
    if not material_ui.manager(parent):return ttk.Label(parent,**kwargs)
    style=ttk.Style(parent);name=kwargs.pop('style','TLabel')
    kwargs.setdefault('font',style.lookup(name,'font') or ('Golos Text',11))
    kwargs.setdefault('fg',style.lookup(name,'foreground') or material_ui.manager(parent).palette['fg'])
    kwargs.setdefault('anchor','w')
    padding=kwargs.pop('padding',None)
    if isinstance(padding,(int,float)):kwargs.update(padx=padding,pady=padding)
    return material_ui.Label(parent,**kwargs)


def NativeButton(parent,**kwargs):
    mgr=material_ui.manager(parent)
    return Button(parent,mgr.palette,**kwargs) if mgr else tk.Button(parent,**kwargs)


def TtkButton(parent,**kwargs):
    mgr=material_ui.manager(parent)
    if not mgr:return ttk.Button(parent,**kwargs)
    name=kwargs.pop('style','TButton');style=ttk.Style(parent)
    active='Active' in name or name.startswith('A.')
    kwargs.setdefault('bg',mgr.palette['raise'] if active else mgr.palette['deep'])
    kwargs.setdefault('fg',mgr.palette['fg'] if active else style.lookup(name,'foreground') or mgr.palette['fg'])
    kwargs.setdefault('font',style.lookup(name,'font') or ('Golos Text',11))
    padding=kwargs.pop('padding',None)
    if isinstance(padding,(int,float)):kwargs.setdefault('padx',padding);kwargs.setdefault('pady',padding)
    return Button(parent,mgr.palette,**kwargs)


def Checkbutton(parent,**kwargs):
    return material_ui.Toggle(parent,**kwargs) if material_ui.manager(parent) else ttk.Checkbutton(parent,**kwargs)


def Radiobutton(parent,**kwargs):
    return material_ui.Toggle(parent,radio=True,**kwargs) if material_ui.manager(parent) else ttk.Radiobutton(parent,**kwargs)


class Surface(material_ui.Frame):
    def __init__(self,parent,palette,**kwargs):
        self.palette=dict(palette)
        kwargs.setdefault('bg',palette['panel'])
        kwargs.setdefault('material_role','panel')
        kwargs['highlightthickness']=0
        super().__init__(parent,**kwargs)

    def _material_image(self,width,height):
        self._material_layer=True
        return material_ui.glass(material_ui.sample(self,width,height),self.palette['panel'],self.palette['gold'],role=self.material_role or 'panel')


class Button(tk.Canvas):
    """A dimensional face with native geometry, focus and keyboard activation."""
    def __init__(self,parent,palette,**options):
        self.palette=dict(palette)
        self.options=dict(text='',command=None,state='normal',fg=palette['fg'],
                          bg=palette['deep'],font=('Golos Text',11),padx=10,pady=7,
                          activebackground=palette['raise'],activeforeground=palette['fg'])
        self.options.update(options)
        self.photo=None
        self.hover=False
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,
                         takefocus=options.get('takefocus',1),cursor=options.get('cursor','hand2'))
        self.resize_request()
        self.bind('<Configure>',self.paint)
        self.bind('<Map>',self.paint)
        self.bind('<Enter>',lambda e:self.hovered(True))
        self.bind('<Leave>',lambda e:self.hovered(False))
        self.bind('<ButtonRelease-1>',lambda e:self.invoke())
        self.bind('<Return>',lambda e:self.invoke())
        self.bind('<space>',lambda e:self.invoke())
        self.bind('<FocusIn>',self.paint)
        self.bind('<FocusOut>',self.paint)

    def resize_request(self):
        font=tkfont.Font(font=self.options['font'])
        lines=str(self.options['text']).splitlines() or ['']
        width=max(font.measure(line) for line in lines)+2*int(self.options['padx'])+6
        if self.options.get('image'):
            width+=int(self.tk.call('image','width',self.options['image']))+6
        if self.options.get('width'):width=max(width,int(self.options['width'])*font.measure('0'))
        height=font.metrics('linespace')*len(lines)+2*int(self.options['pady'])+4
        super().configure(width=width,height=height)

    def configure(self,cnf=None,**kwargs):
        if cnf:
            kwargs.update(cnf)
        if not hasattr(self,'options'):
            return super().configure(**kwargs)
        self.options.update(kwargs)
        if any(key in kwargs for key in ('text','font','padx','pady','image','width')):
            self.resize_request()
        if self.winfo_exists():
            self.paint()
    config=configure

    def cget(self,key):
        if hasattr(self,'options') and key in self.options:
            return self.options[key]
        return super().cget(key)

    def hovered(self,value):
        self.hover=value
        self.paint()

    def invoke(self):
        if self.options.get('state')!='disabled':
            command=self.options.get('command')
            if command:
                return command()

    def paint(self,event=None):
        if not self.winfo_exists() or not self.winfo_ismapped():
            return
        width,height=self.winfo_width(),self.winfo_height()
        if min(width,height)<4:
            return
        fill=self.options['activebackground'] if self.hover else self.options['bg']
        colour=self.options['activeforeground'] if self.hover else self.options['fg']
        if self.options.get('state')=='disabled':
            colour=self.palette['mute']
        image=material_ui.glass(material_ui.sample(self,width,height),fill,self.palette['gold'],active=self.options['bg']==self.palette['raise'] or self.hover,role='button')
        self.photo=ImageTk.PhotoImage(image,master=self)
        self.delete('all')
        self.create_image(0,0,anchor='nw',image=self.photo)
        text_x=width/2
        if self.options.get('image'):
            iw=int(self.tk.call('image','width',self.options['image']))
            tw=tkfont.Font(font=self.options['font']).measure(self.options['text'])
            x=(width-iw-6-tw)/2
            self.create_image(x,height/2,image=self.options['image'],anchor='w')
            text_x=x+iw+6+tw/2
        self.create_text(text_x,height/2,text=self.options['text'],font=self.options['font'],
                         fill=colour,justify='center')
        if self.focus_get() is self:
            self.create_rectangle(3,3,width-4,height-4,outline=self.palette['gold'],dash=(2,2))


def install_controls(app,style):
    # Standard ttk fallbacks remain available for windows without a material
    # manager. Main-window buttons use a full-size canvas face, never tiled art.
    app._skin_images=[]
    style.configure('TButton',foreground=app.skin_palette['fg'],padding=(14,7))
    style.map('TButton',foreground=[('disabled',app.skin_palette['mute'])])
    install_fields(app,style)


def field_face(width,height,palette,focused=False):
    """Soft recessed field; native ttk still draws text, selection and caret."""
    ss=3;w,h=max(4,width),max(4,height)
    mask=Image.new('L',(w*ss,h*ss))
    ImageDraw.Draw(mask).rounded_rectangle((ss,ss,(w-1)*ss,(h-1)*ss),radius=8*ss,fill=255)
    mask=mask.resize((w,h),Image.Resampling.LANCZOS)
    face=Image.new('RGBA',(w,h));d=ImageDraw.Draw(face)
    for y in range(h):
        t=y/max(1,h-1)
        color=material_ui.mix(palette['deep'],palette['gold'],.21*(1-t)**2+.055)
        d.line((0,y,w,y),fill=color+(255,))
    face.putalpha(mask)
    edge=Image.new('RGBA',(w*ss,h*ss));d=ImageDraw.Draw(edge)
    rim=palette['gold'] if focused else material_ui.mix(palette['deep'],palette['gold'],.40)
    d.rounded_rectangle((ss,ss,(w-1)*ss,(h-1)*ss),radius=8*ss,outline=rim,width=ss)
    d.line((9*ss,2*ss,(w-9)*ss,2*ss),fill=material_ui.mix(palette['deep'],palette['gold'],.48),width=ss)
    face.alpha_composite(edge.resize((w,h),Image.Resampling.LANCZOS))
    return face


def install_fields(app,style):
    """Keep ttk semantics while changing only its field and arrow elements.

    Installed once per theme rebuild, not on every search/history refresh.
    Native textarea elements are essential: omitting them hides selected values.
    """
    p=app.skin_palette;root=app.root;scale=app.s['scale']/100
    px=lambda n:max(1,round(n*scale))
    revision=getattr(root,'_field_revision',0)+1;root._field_revision=revision
    prefix=f'Blossom{revision}'
    photos=[ImageTk.PhotoImage(field_face(px(72),px(34),p,focused),master=root) for focused in (False,True)]
    arrow=Image.new('RGBA',(px(24)*3,px(18)*3));d=ImageDraw.Draw(arrow)
    d.line([(px(x)*3,px(y)*3) for x,y in ((7,7),(12,12),(17,7))],fill=p['mute'],width=max(3,px(1)*3))
    photos.append(ImageTk.PhotoImage(arrow.resize((px(24),px(18)),Image.Resampling.LANCZOS),master=root))
    root._field_images=photos
    style.element_create(prefix+'.field','image',photos[0],('focus',photos[1]),
                         border=(px(10),px(5),px(10),px(5)),sticky='nswe')
    style.element_create(prefix+'.downarrow','image',photos[2],sticky='')
    style.layout('History.TCombobox',[(prefix+'.field',{'sticky':'nswe','children':[
        (prefix+'.downarrow',{'side':'right','sticky':'ns'}),
        ('Combobox.padding',{'sticky':'nswe','children':[('Combobox.textarea',{'sticky':'nswe'})]})]})])
    style.layout('History.TEntry',[(prefix+'.field',{'sticky':'nswe','children':[
        ('Entry.padding',{'sticky':'nswe','children':[('Entry.textarea',{'sticky':'nswe'})]})]})])
    # ttk fills transparent image corners with its style background. Match the
    # surrounding material instead of exposing white squares in the day theme.
    surrounding=material_ui.glass(Image.new('RGB',(72,34),p['bg']),p['panel'],p['gold']).getpixel((36,22))
    surrounding='#'+''.join(f'{channel:02x}' for channel in surrounding)
    for name in ('History.TEntry','History.TCombobox'):
        style.configure(name,foreground=p['fg'],background=surrounding,fieldbackground=p['deep'],
                        insertcolor=p['fg'],borderwidth=0,padding=(px(3),px(3)))
        style.map(name,foreground=[('disabled',p['mute']),('readonly',p['fg'])],
                  fieldbackground=[('readonly',p['deep'])],
                  selectbackground=[('!focus',p['deep']),('focus',p['raise'])],
                  selectforeground=[('!focus',p['fg']),('focus',p['fg'])])


def casing_texture(width,height,palette,scale):
    """One continuous bevel, cropped by the shell into static edge images."""
    if palette['dark'] and palette['bg']=='#180f22':
        artwork=material_ui.material_assets.shell(width,height,scale)
        if artwork is not None:return artwork
    ss=2;w,h=width*ss,height*ss
    outer=round(11*scale*ss);thickness=round(15*scale*ss);cut=round(22*scale*ss)
    image=Image.new('RGB',(w,h),'#0d0a11' if palette['dark'] else '#e4dce8')
    def polygon(inset,rounded=True):
        x,y=outer+inset,outer+inset;r=cut
        vertices=[(x+r,y),(w-x-r-1,y),(w-x-1,y+r),(w-x-1,h-y-r-1),
                  (w-x-r-1,h-y-1),(x+r,h-y-1),(x,h-y-r-1),(x,y+r)]
        if not rounded:return vertices
        points=[];soft=8*scale*ss
        for j,vertex in enumerate(vertices):
            prev,nxt=vertices[j-1],vertices[(j+1)%8]
            def approach(other):
                length=math.hypot(other[0]-vertex[0],other[1]-vertex[1])
                t=min(.3,soft/max(1,length))
                return (vertex[0]+t*(other[0]-vertex[0]),vertex[1]+t*(other[1]-vertex[1]))
            a,b=approach(prev),approach(nxt)
            for step in range(9):
                t=step/8
                points.append(((1-t)**2*a[0]+2*t*(1-t)*vertex[0]+t*t*b[0],
                               (1-t)**2*a[1]+2*t*(1-t)*vertex[1]+t*t*b[1]))
        return points
    background=material_ui.atmosphere(width,height,palette['bg'],palette['gold'],palette['dark']).resize((w,h),Image.Resampling.BICUBIC)
    mask=Image.new('L',(w,h));ImageDraw.Draw(mask).polygon(polygon(0),fill=255)
    image.paste(background,(0,0),mask)
    d=ImageDraw.Draw(image)
    stops=[(0,.27),(.07,.68),(.18,.95),(.28,.52),(.43,.66),(.56,.34),(.74,.31),(.88,.67),(1,.28)]
    for i in range(thickness):
        t=i/max(1,thickness-1)
        for (a,va),(b,vb) in zip(stops,stops[1:]):
            if a<=t<=b:shine=va+(vb-va)*(t-a)/(b-a);break
        points=polygon(i)
        for index,(start,end) in enumerate(zip(points,points[1:]+points[:1])):
            dx,dy=end[0]-start[0],end[1]-start[1];length=max(1,math.hypot(dx,dy))
            light=.9+.1*dx/length-.08*dy/length
            steps=max(1,round(length/(12*ss)))
            for step in range(steps):
                t0,t1=step/steps,(step+1)/steps
                a=(start[0]+dx*t0,start[1]+dy*t0);b=(start[0]+dx*t1,start[1]+dy*t1)
                nx,ny=(a[0]+b[0])/(2*w),(a[1]+b[1])/(2*h)
                hue=material_ui.mix('#df95be','#9980c8',nx)
                colour=material_ui.mix('#2b1939',hue,min(1,shine*light))
                if shine>.82:colour=material_ui.mix(colour,'#fff0f9',(shine-.82)*3.9)
                glint=(.55*math.exp(-(((nx-.025)/.036)**2+((ny-.025)/.06)**2))+
                       .29*math.exp(-(((nx-.98)/.03)**2+((ny-.035)/.07)**2))+
                       .35*math.exp(-(((nx-.98)/.03)**2+((ny-.97)/.07)**2))+
                       .18*math.exp(-(((nx-.02)/.035)**2+((ny-.96)/.09)**2)))
                colour=material_ui.mix(colour,'#ffe4f4',glint*(.4+.6*shine))
                if not palette['dark']:colour=material_ui.mix(colour,'#f2e5f4',.35)
                d.line((a,b),fill=colour,width=2)
    # Jewel-like joins expose the change of plane at the cut corners.
    outside,inside=polygon(1,False),polygon(thickness-2,False)
    for index in (0,1,2,3,4,5,6,7):
        d.line((outside[index],inside[index]),fill='#c49dcf',width=1)
    return image.resize((width,height),Image.Resampling.LANCZOS)


def install_shell(app, palette, window=None):
    """Decorative casing inside the native resizable Windows frame."""
    root=window or app.root
    scale=app.s['scale']/100
    material_ui.Manager(root,palette,scale)
    edge=max(18,round(28*scale));size=max(edge,round(54*scale))
    sides={}
    for side in ('top','bottom','left','right'):
        horizontal=side in ('top','bottom')
        canvas=tk.Canvas(root,bg=palette['bg'],bd=0,highlightthickness=0,
                         height=edge if horizontal else 1,width=1 if horizontal else edge)
        canvas.pack(side=side,fill='x' if horizontal else 'y');sides[side]=canvas
    caps={}
    for location in ('nw','ne','sw','se'):
        cap=tk.Label(root,bd=0,highlightthickness=0,bg=palette['bg'],takefocus=0)
        cap.place(relx=1 if 'e' in location else 0,rely=1 if 's' in location else 0,anchor=location)
        caps[location]=cap
    pending=None;signature=None
    def paint():
        nonlocal pending,signature
        pending=None
        if not root.winfo_exists():return
        width,height=root.winfo_width(),root.winfo_height()
        if min(width,height)<2*size or signature==(width,height):return
        signature=(width,height)
        full=casing_texture(width,height,palette,scale)
        boxes={'top':(0,0,width,edge),'bottom':(0,height-edge,width,height),
               'left':(0,edge,edge,height-edge),'right':(width-edge,edge,width,height-edge)}
        for side,canvas in sides.items():
            if not canvas.winfo_exists():return
            canvas.photo=ImageTk.PhotoImage(full.crop(boxes[side]),master=canvas)
            canvas.delete('all');canvas.create_image(0,0,anchor='nw',image=canvas.photo)
        for location,cap in caps.items():
            x=width-size if 'e' in location else 0;y=height-size if 's' in location else 0
            cap.photo=ImageTk.PhotoImage(full.crop((x,y,x+size,y+size)),master=cap)
            cap.configure(image=cap.photo);cap.lift()
    def resize(event):
        nonlocal pending
        if event.widget is root and pending is None:pending=root.after_idle(paint)
    # A theme rebuild destroys the prior edge canvases; replace its root binding.
    prior=getattr(root,'_casing_binding',None)
    if prior:
        try:root.unbind('<Configure>',prior)
        except tk.TclError:pass
    root._casing_binding=root.bind('<Configure>',resize,add='+')
    root.after_idle(paint)
    if __import__('os').name=='nt':
        import ctypes
        root.update_idletasks()
        hwnd=ctypes.windll.user32.GetParent(root.winfo_id())
        colour=render.rgb(palette['deep'])
        value=ctypes.c_int(colour[0]|colour[1]<<8|colour[2]<<16)
        # Supported on Windows 11; older versions simply keep their native title bar.
        ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd),35,ctypes.byref(value),4)


def section(parent,app,title):
    frame=Surface(parent,app.skin_palette,bg=app.skin_palette['bg'],
                  padx=app.fs(14),pady=app.fs(12))
    frame.pack(fill='x',pady=(0,app.fs(12)))
    Label(frame,text=title,bg=app.skin_palette['bg'],fg=app.skin_palette['gold'],
             font=('Forum',app.fs(18)),anchor='w').pack(fill='x',pady=(0,app.fs(9)))
    return frame
