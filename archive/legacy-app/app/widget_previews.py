"""Preview images produced by the existing overlay demo/draw methods; no live windows."""
import copy
from types import SimpleNamespace,MethodType
import time


def render_preview(app,key):
    import ui
    if ui.Image is None:return None
    settings=copy.deepcopy(dict(app.s));settings.update(scale=100,alpha=100)
    proxy=SimpleNamespace(s=settings,data=app.data,icons=app.icons,hidden=True,last_game=None)
    proxy.pimg=lambda group,ident,*a,**kw:ui.App.pimg(proxy,group,ident,*a,**kw) if str(ident) in app.icons.a.get(group,{}) else None
    if key=='tab':
        vals=((9800,8950),(7400,7720),(10300,10300),(11800,10560),(5200,5290))
        rows=[({'v':a},{'v':b}) for a,b in vals]
        # Enlarge actual overlay fragments: the real table's centre gutter is too
        # narrow to read when the entire scoreboard is shrunk into a card.
        im=ui.render.tab_plates((10,80,1000,300),[],ui.C,1,totals=(sum(a for a,b in vals),sum(b for a,b in vals)))
        bounds=im.getbbox();banner=im.crop(bounds)
        canvas=ui.Image.new('RGBA',(max(440,banner.width),150),(0,0,0,0))
        canvas.alpha_composite(banner,((canvas.width-banner.width)//2,0))
        for i,(a,b) in enumerate(rows):
            text,direction,color=ui.render.tab_advantage(a,b)
            badge=ui.render.hud_badge(text,direction,color,40,66)
            canvas.alpha_composite(badge,(40+i*80,70))
        return canvas
    cls={'hints':ui.HintsOverlay,'perf':ui.PerfOverlay,'lane':ui.LaneOverlay,'inventory':ui.InventoryOverlay,
         'item':ui.ItemOverlay,'timers':ui.TimersOverlay,'arena':ui.ArenaOverlay}[key]
    preview=SimpleNamespace(app=proxy,key=key,image=None,CAPS=ui.Overlay.CAPS,deiconify=lambda:None,withdraw=lambda:None,unlocked=False)
    preview.card=MethodType(ui.Overlay.card,preview)
    preview.put=lambda card:setattr(preview,'image',card.render())
    for name in ('draw','draw_plan','values_card'):
        if hasattr(cls,name):setattr(preview,name,MethodType(getattr(cls,name),preview))
    if key=='hints':
        preview.items=[(time.time(),'Дракон через 45 секунд. Подготовь обзор у реки.','fg','12:40')];cls.show(preview)
    else:cls.demo(preview)
    return preview.image
