"""Shared native-screen primitives using the app's existing palette and game assets."""
import tkinter as tk


class Components:
    def label(self,parent,text,size=10,color='fg',head=False,num=False,**kw):
        return tk.Label(parent,text=text,bg=kw.pop('bg',parent.cget('bg')),fg=self.c[color],
                        font=(self.f['head'] if head else self.f['numb'] if num else self.f['font'],self.app.fs(size)),anchor=kw.pop('anchor','w'),**kw)

    def button(self,parent,text,command,on=False):
        c=self.c
        return tk.Button(parent,text=text,command=command,bg=c['raise'] if on else c['deep'],fg=c['gold'] if on else c['mute'],
                         relief='flat',bd=0,highlightthickness=1,highlightbackground=c['gold'] if on else c['line'],
                         highlightcolor=c['gold'],activebackground=c['raise'],activeforeground=c['gold'],
                         font=(self.f['font'],self.app.fs(10)),padx=self.app.fs(10),pady=self.app.fs(7),cursor='hand2')

    def panel(self,parent,pad=12):
        return tk.Frame(parent,bg=self.c['panel'],padx=self.app.fs(pad),pady=self.app.fs(pad),
                        highlightthickness=1,highlightbackground=self.c['line'])

    def image(self,parent,group,key,size):
        if key is None or str(key) not in self.app.icons.a.get(group,{}):return None
        photo=self.app.icons.get(group,str(key),self.app.fs(size))
        if photo:
            label=tk.Label(parent,image=photo,bg=parent.cget('bg'));label.pack(side='left',padx=(0,self.app.fs(5)))
            return label

    def item_icons(self,parent,items,size=22):
        for item in items:
            if not item:continue
            if not self.image(parent,'item',item,size):
                self.label(parent,'#'+str(item),7,'mute').pack(side='left',padx=(0,3))


def readable_palette(colors):
    """Локальный контраст пояснений без изменения глобальной темы."""
    result=dict(colors);fg,bg=result['fg'],result['panel']
    result['mute']='#'+''.join(f'{round(int(fg[i:i+2],16)*.8+int(bg[i:i+2],16)*.2):02x}' for i in (1,3,5))
    return result


class ReadableComponents(Components):
    """Крупные подписи для обычных страниц, без влияния на игровые оверлеи."""
    def label(self,parent,text,size=11,color='fg',**kw):
        return super().label(parent,text,max(11,size),color,**kw)

    def button(self,parent,text,command,on=False):
        button=super().button(parent,text,command,on)
        button.configure(font=(self.f['font'],self.app.fs(11)),fg=self.c['gold'] if on else self.c['fg'])
        return button
