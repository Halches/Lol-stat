"""Static dimensional surfaces and controls shared by the desktop screens."""
import tkinter as tk
from tkinter import ttk, font as tkfont
from functools import lru_cache
from PIL import Image, ImageDraw, ImageTk
import render


@lru_cache(maxsize=24)
def surface_image(width, height, fill, edge, accent, raised=False):
    width, height = max(4, width), max(4, height)
    image = Image.new('RGB', (width, height), fill)
    draw = ImageDraw.Draw(image)
    base, light = render.rgb(fill), render.rgb(accent)
    # The centre stays the exact palette colour used by child labels and entries.
    depth = min(18 if raised else 12, height//3)
    for y in range(depth):
        amount = (.22 if raised else .10) * (1-y/max(1, depth))
        colour = tuple(round(a*(1-amount)+b*amount) for a,b in zip(base, light))
        draw.line((1,y,width-2,y), fill=colour)
    draw.rounded_rectangle((0,0,width-1,height-1), radius=min(9,height//3),
                           outline=edge, width=1)
    draw.line((9,1,max(9,width-10),1), fill=accent)
    draw.line((8,height-2,max(8,width-9),height-2), fill=tuple(round(v*.65) for v in base))
    return image


class Surface(tk.Frame):
    """Native child widgets retain their existing geometry, focus and bindings."""
    def __init__(self, parent, palette, **kwargs):
        self.palette = dict(palette)
        kwargs.setdefault('bg', palette['panel'])
        kwargs.setdefault('highlightbackground', palette['line'])
        kwargs.setdefault('highlightthickness', 1)
        super().__init__(parent, **kwargs)
        self.art = tk.Label(self, bd=0, bg=self.cget('bg'), takefocus=0)
        self.art.place(x=0,y=0,relwidth=1,relheight=1)
        self.art.bindtags((str(self), *self.art.bindtags()[1:]))
        self.photo = None
        self.signature = None
        self.bind('<Configure>', self.paint, add='+')

    def paint(self, event):
        if event.widget is not self or min(event.width,event.height)<4:
            return
        signature=(event.width,event.height,self.cget('bg'))
        if signature == self.signature:
            return
        image=surface_image(*signature,self.palette['line'],self.palette['gold'])
        self.photo=ImageTk.PhotoImage(image,master=self)
        self.art.configure(image=self.photo)
        self.art.lower()
        self.signature=signature


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
        self.bind('<Enter>',lambda e:self.hovered(True))
        self.bind('<Leave>',lambda e:self.hovered(False))
        self.bind('<Button-1>',lambda e:self.invoke())
        self.bind('<Return>',lambda e:self.invoke())
        self.bind('<space>',lambda e:self.invoke())
        self.bind('<FocusIn>',self.paint)
        self.bind('<FocusOut>',self.paint)

    def resize_request(self):
        font=tkfont.Font(font=self.options['font'])
        lines=str(self.options['text']).splitlines() or ['']
        width=max(font.measure(line) for line in lines)+2*int(self.options['padx'])+6
        height=font.metrics('linespace')*len(lines)+2*int(self.options['pady'])+4
        super().configure(width=width,height=height)

    def configure(self,cnf=None,**kwargs):
        if cnf:
            kwargs.update(cnf)
        if not hasattr(self,'options'):
            return super().configure(**kwargs)
        self.options.update(kwargs)
        if any(key in kwargs for key in ('text','font','padx','pady')):
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
        if not self.winfo_exists():
            return
        width,height=self.winfo_width(),self.winfo_height()
        if min(width,height)<4:
            return
        fill=self.options['activebackground'] if self.hover else self.options['bg']
        colour=self.options['activeforeground'] if self.hover else self.options['fg']
        if self.options.get('state')=='disabled':
            colour=self.palette['mute']
        image=surface_image(width,height,fill,self.palette['line'],self.palette['gold'],True)
        self.photo=ImageTk.PhotoImage(image,master=self)
        self.delete('all')
        self.create_image(0,0,anchor='nw',image=self.photo)
        self.create_text(width/2,height/2,text=self.options['text'],font=self.options['font'],
                         fill=colour,justify='center')
        if self.focus_get() is self:
            self.create_rectangle(3,3,width-4,height-4,outline=self.palette['gold'],dash=(2,2))


def install_controls(app, style):
    """Nine-slice images keep controls dimensional at any window width."""
    app._skin_images=[]
    for name,raised in (('TButton',False),('A.TButton',True)):
        photos=[]
        for active in (False,True):
            fill=app.skin_palette['raise' if active or raised else 'panel']
            photo=ImageTk.PhotoImage(surface_image(48,32,fill,app.skin_palette['line'],
                                                   app.skin_palette['gold'],raised or active),master=app.root,
                                    name='blossom_'+name.replace('.','_')+'_'+str(int(active)))
            photos.append(photo);app._skin_images.append(photo)
        element='Blossom.'+name
        if element not in style.element_names():
            style.element_create(element,'image',photos[0],('active',photos[1]),
                                 border=9,sticky='nsew')
        style.layout(name,[(element,{'sticky':'nsew','children':[
            ('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
        style.configure(name,foreground=app.skin_palette['fg'],padding=(14,7))
        style.map(name,foreground=[('disabled',app.skin_palette['mute']),('active',app.skin_palette['fg'])])


def install_shell(app, palette):
    """A narrow internal casing preserves native resize, snap and window controls."""
    edge=max(4,round(7*app.s['scale']/100))
    for side in ('top','bottom','left','right'):
        horizontal=side in ('top','bottom')
        canvas=tk.Canvas(app.root,bg=palette['deep'],bd=0,highlightthickness=0,
                         height=edge if horizontal else 1,width=1 if horizontal else edge)
        canvas.pack(side=side,fill='x' if horizontal else 'y')
        def paint(event,canvas=canvas,horizontal=horizontal):
            canvas.delete('all')
            length=event.width if horizontal else event.height
            for i in range(edge):
                mix=1-abs(i-edge*.43)/max(1,edge*.57)
                colour=tuple(round(a*(1-mix*.65)+b*mix*.65)
                             for a,b in zip(render.rgb(palette['deep']),render.rgb(palette['gold'])))
                coords=(0,i,length,i) if horizontal else (i,0,i,length)
                canvas.create_line(*coords,fill='#%02x%02x%02x'%colour)
        canvas.bind('<Configure>',paint)
    if __import__('os').name=='nt':
        import ctypes
        app.root.update_idletasks()
        hwnd=ctypes.windll.user32.GetParent(app.root.winfo_id())
        colour=render.rgb(palette['deep'])
        value=ctypes.c_int(colour[0]|colour[1]<<8|colour[2]<<16)
        # Supported on Windows 11; older versions simply keep their native title bar.
        ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd),35,ctypes.byref(value),4)


def section(parent,app,title):
    frame=Surface(parent,app.skin_palette,bg=app.skin_palette['bg'],
                  padx=app.fs(14),pady=app.fs(12))
    frame.pack(fill='x',pady=(0,app.fs(12)))
    tk.Label(frame,text=title,bg=app.skin_palette['bg'],fg=app.skin_palette['gold'],
             font=('Forum',app.fs(18)),anchor='w').pack(fill='x',pady=(0,app.fs(9)))
    return frame
