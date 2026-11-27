"""Qt-окно перевеса: прежние расчёты и распознавание Tab."""
import time,threading,queue
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QLabel
import render,core,tab_detect
from app_config import C,IS_WIN,game_rect,game_focused,screens,tab_rect_drag,log_error
from .overlay_base import Overlay
from . import native

class Handle(QLabel):
    def __init__(self,owner):
        super().__init__('TAB · тяни | Shift: размер',None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.owner=owner;self.drag=None;self.resize(240,26)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet('background:#674878;color:#fff0ff;padding:4px;')
    def mousePressEvent(self,e):
        self.owner.auto_layout=None
        self.drag=(native.cursor(),list(self.owner.rect()),max(1,game_rect()[3]),bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier))
    def mouseMoveEvent(self,e):
        if not self.drag:return
        p,rect,h,resize=self.drag;delta=native.cursor()-p
        self.owner.app.s['tab_rect']=tab_rect_drag(rect,delta.x()/h,delta.y()/h,resize)
        if self.owner.data:self.owner.draw(*self.owner.data)
    def mouseReleaseEvent(self,e):
        if self.drag:self.drag=None;self.owner.app.s.save()

class TabPlates(Overlay):
    def __init__(self,app):
        super().__init__(app,'tab',(0,0))
        self.data,self._geometry_sig=None,None
        self.auto_layout,self._auto_context=None,None
        self._auto_results,self._auto_cancel=queue.Queue(),threading.Event()
        self._auto_pending,self._auto_active=False,False
        self._auto_epoch,self._auto_next,self._auto_time=0,0.,0.
        self.auto_status='Автоподгонка: ожидаю Tab в игре';self._left_ally=True
        self.handle=Handle(self);self.withdraw()
    def draw(self,rows):
        X,Y,W,H,side,tp=self.geom();scale=self.k()
        signature=(X,Y,W,H,side,tp,scale,self.unlocked,self._left_ally,self.__dict__.get('totals'),tuple(sorted(C.items())),tuple(tuple(p['v'] if p else None for p in row) for row in rows))
        if signature==getattr(self,'_tab_draw_signature',None):return
        im=render.tab_plates((side,tp,W,H),rows,C,scale,frame=self.unlocked,left_ally=self._left_ally,totals=self.__dict__.get('totals'))
        self.put_image(im);self.move_physical(int(X-side),int(Y-tp))
        self._geometry_sig=(game_rect(),tuple(self.rect()),self.app.s['scale']);self._place_handle();self._tab_draw_signature=signature
    def _place_handle(self):
        if not hasattr(self,'handle'):return
        visible=self.unlocked and self.isVisible() and not(self.app.s.get('tab_auto') and self.auto_layout)
        self.handle.setVisible(visible)
        if visible:x,y,_,_=native.geometry(self);native.move(self.handle,x,y-round(32*self.devicePixelRatioF()));native.styles(self.handle,False);self.handle.raise_()
    def deiconify(self):super().deiconify();self._place_handle()
    def withdraw(self):
        if hasattr(self,'handle'):self.handle.hide()
        super().withdraw()
    def unlock(self,on):
        super().unlock(on)
        if hasattr(self,'data') and self.data and self.isVisible():self.draw(*self.data)
        self._place_handle()
    def _detection_status(self,text):
        self.auto_status=text
        label=getattr(self.app,'tab_auto_label',None)
        if label:label.setText(text)
    def closeEvent(self,event):
        self._auto_cancel.set();self.handle.close();self.handle.deleteLater();super().closeEvent(event)
    def rect(self):
        if self.app.s.get('tab_auto') and self.auto_layout: return self.auto_layout.rect
        r = self.app.s.get('tab_rect')
        if r: return r
        dx, y = self.app.s['tab_pos'].get('tabgold', [-.553, .288])
        return [dx, y, -2 * dx, 5 * self.app.s['tab_step'] / 1080]

    def k(self):
        return game_rect()[3] / 1080 * self.app.s['scale'] / 100

    def geom(self):
        gx, gy, gw, gh = game_rect()
        l, t, w, h = self.rect()
        side = 0
        top = round(h*gh*.35+max(30,h*gh*.22)) if self.__dict__.get('totals') is not None else 0
        return gx + gw / 2 + l * gh, gy + t * gh, w * gh, h * gh, side, top

    def refresh_geometry(self):
        sig = (game_rect(), tuple(self.rect()), self.app.s['scale'])
        if self.data and sig != self._geometry_sig: self.draw(*self.data)

    def show(self, g):
        rows = []
        layout = self.auto_layout if self.app.s.get('tab_auto') else None
        self._left_ally = not layout or layout.teams[0] == g.my_team
        left = g.allies if self._left_ally else g.enemies
        right = g.enemies if self._left_ally else g.allies
        self.totals = (sum(p['igold'] for p in left), sum(p['igold'] for p in right)) if left and right else None
        for i, r in enumerate(core.ROLES):
            a = next((p for p in left if (p['c'] == layout.columns[0][i] if layout else p['pos'] == r)), None)
            e = next((p for p in right if (p['c'] == layout.columns[1][i] if layout else p['pos'] == r)), None)
            # Compare the two visible players in this row, including manual reordering.
            rows.append(({'v': a['igold']} if a else None, {'v': e['igold']} if e else None))
        self.data = (rows,)
        self.draw(*self.data)

    def auto_tick(self, active, g):
        """Called only on Tk's thread. Workers return plain data through a queue."""
        now = time.monotonic()
        # Practice/custom games can have fewer than ten players. The frame detector
        # validates those without inventing the missing portraits.
        active = bool(active and IS_WIN and self.app.s.get('tab_auto') and g and g.players)
        context = (game_rect(), tuple(sorted((p['riot'], p['c'], p['team']) for p in g.players))) if g else None
        reset = context != self._auto_context or (g and g.t < self._auto_time)
        if reset or active != self._auto_active:
            self._auto_cancel.set()
            self._auto_epoch += 1
            self._auto_next = now + .20  # allow the game's opening animation to finish
            if active: self._detection_status(f'Автоподгонка: запускаю поиск · игроков {len(g.players)}')
        if reset: self.auto_layout = None
        self._auto_context, self._auto_active = context, active
        self._auto_time = g.t if g else 0
        while not self._auto_results.empty():
            epoch, result, error = self._auto_results.get_nowait()
            self._auto_pending = False
            if epoch != self._auto_epoch or not active: continue
            if error:
                log_error('Tab: автоподгонка', error)
                self._detection_status('Автоподгонка недоступна; используется сохранённая рамка')
            elif result:
                self.auto_layout = result
                known = sum(c is not None for col in result.columns for c in col)
                source = 'по рамке' if result.source == 'frame' else 'по портретам'
                self._detection_status(f'Таблица найдена {source} · распознаны строки {known}/{len(g.players)}')
                self.show(g)
            else:
                self._detection_status('Таблица не распознана · последняя рамка; ручная настройка через Alt')
        if not self.app.s.get('tab_auto'):
            self._detection_status('Автоподгонка выключена · ручная настройка через Tab + Alt')
        elif not g or not g.players:
            self._detection_status('Автоподгонка: ожидаю игровые данные от клиента LoL')
        if not active or self._auto_pending or now < self._auto_next: return
        self._auto_next, self._auto_pending = now + 2.5, True
        if not self.auto_layout:
            self._detection_status(f'Автоподгонка: ищу таблицу · игроков {len(g.players)}')
        self._auto_cancel = cancel = threading.Event()
        epoch, results = self._auto_epoch, self._auto_results
        rect = context[0]
        players = [dict(p) for p in g.players]
        portraits = dict(getattr(self.app.icons, 'a', {}).get('champ', {}))
        def work():
            result, error = None, None
            try:
                if not cancel.is_set() and game_focused() and game_rect() == rect:
                    result = tab_detect.capture_and_detect(rect, portraits, players, cancel)
            except Exception as e: error = str(e)
            results.put((epoch, result, error))
        threading.Thread(target=work, daemon=True, name='tab-detection').start()

    def demo(self):
        self._left_ally = True
        vals = ((9800, 8950), (7400, 7720), (10300, 10300), (11800, 10560), (5200, 5290))
        self.totals = (sum(a for a,_ in vals),sum(b for _,b in vals))
        rows = [({'v': a}, {'v': e}) for a, e in vals]
        self.data = (rows,)
        self.draw(*self.data)
