# Драфт на телефоне: маленький веб-сервер в домашней сети. Телефон открывает адрес из настроек и видит
# то же, что второе окно в драфте: кого брать, кого банить, руны, сборку, умения. Кнопка импортирует в клиент.
import json, secrets, socket, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html lang=ru><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>LoL Helper — драфт</title><style>
:root{--bg:#0A0E14;--panel:#111824;--line:#223044;--fg:#E8EDF4;--mute:#8A97A8;--gold:#D6B46A;--blue:#4FA3FF;--red:#FF7A45;--good:#4FD18B;--bad:#FF6B6B}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif;padding:14px 16px 90px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mute);font-size:13px;margin-bottom:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:10px 0}
.cap{color:var(--gold);font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px}
.row{display:flex;justify-content:space-between;gap:10px;padding:3px 0}.mute{color:var(--mute)}.big{font-size:28px;font-weight:700}
.chip{display:inline-block;background:#1A2433;border-radius:6px;padding:2px 7px;margin:2px 3px 2px 0;font-size:13px}
.r{background:var(--gold);color:#14100A;font-weight:700}
footer{position:fixed;left:0;right:0;bottom:0;padding:8px 16px 16px;background:var(--bg)}
button{width:100%;padding:14px;border:0;border-radius:10px;background:var(--gold);color:#14100A;font:700 16px system-ui}
button:disabled{opacity:.55}
#connection,#import-status{color:var(--bad);font-size:13px}
#connection:not(:empty){position:sticky;top:0;z-index:1;background:var(--bg);padding:8px 0}
#import-status:not(:empty){margin-bottom:8px}
</style></head><body><div id=connection role=status></div><div id=app class=mute>Жду данные…</div>
<footer id=actions hidden><div id=import-status role=status></div><button id=imp disabled>Импортировать в клиент</button></footer><script>
const T=location.pathname.replace(/\\/$/,''),$=s=>document.querySelector(s),e=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'})[c]);
const button=$('#imp'),actions=$('#actions'),connection=$('#connection'),importStatus=$('#import-status');
let connected=false, importing=false, canImport=false, lastUpdate='';
function syncImport(){actions.hidden=!canImport;button.disabled=!connected||!canImport||importing;}
function disconnected(){
 connected=false;
 connection.textContent='Связь с ПК потеряна'+(lastUpdate?' · последние данные в '+lastUpdate:'');
 syncImport();
}
function request(path,options={}){
 return fetch(T+path,{...options,signal:globalThis.AbortSignal?.timeout?.(5000)});
}
function card(t,b){return b?`<div class=card><div class=cap>${t}</div>${b}</div>`:''}
function draw(s){
 $('#app').className='';
 canImport=s?.mode==='draft'&&Boolean(s.me);
 if(!canImport)importStatus.textContent='';
 if(!s||s.mode!=='draft'){$('#app').innerHTML=`<h1>LoL Helper</h1><div class=sub>${e(s&&s.text||'Ждём выбора чемпионов. Страница обновится сама.')}</div>`;return}
 let h=`<h1>${e(s.title)}</h1><div class=sub>${e(s.sub)}</div>`;
 if(s.mu)h+=card('Твой матчап',`<div class=big>${e(s.mu.wr)}</div><div class=mute>${e(s.mu.text)}</div>`);
 if(s.comp)h+=card('Состав',s.comp.map(x=>`<div>${e(x)}</div>`).join(''));
 if(s.me)h+=card('Сборка · '+e(s.me),`<div class=sub>${e(s.build_source||'')}</div>`+(s.build||[]).map(([k,v])=>`<div class=row><span class=mute>${e(k)}</span><span>${e(v)}</span></div>`).join('')+
   (s.skills?`<div style="margin-top:6px">${[...s.skills].map((k,i)=>`<span class="chip ${k==='R'?'r':''}">${i+1}:${e(k)}</span>`).join('')}</div>`:'')+
   (s.build_status?`<div class=sub>${e(s.build_status)}</div>`:''));
 if(s.picks&&s.picks.length)h+=card('Кого взять',s.picks.map(p=>`<div><b>${e(p[0])}</b> <span class=mute>${e(p[1])}</span></div>`).join(''));
 if(s.bans&&s.bans.length)h+=card('Кого банить',s.bans.map(p=>`<div><b style="color:var(--bad)">${e(p[0])}</b> <span class=mute>${e(p[1])}</span></div>`).join(''));
 if(s.imp)h+=`<div class=sub>${e(s.imp)}</div>`;
 $('#app').innerHTML=h}
async function tick(){
 try{
  const response=await request('/state.json',{cache:'no-store'});
  if(!response.ok)throw Error('Нет данных драфта');
  draw(await response.json());
  lastUpdate=new Date().toLocaleTimeString('ru-RU');
  connected=true;
  connection.textContent='';
  syncImport();
 }catch(_){disconnected();}
 setTimeout(tick,2000);
}
button.onclick=async()=>{
 if(button.disabled)return;
 importing=true;
 importStatus.textContent='';
 button.textContent='Отправляю…';
 syncImport();
 try{
  const response=await request('/import',{method:'POST'});
  if(response.ok)button.textContent='Запрос отправлен на ПК';
  else if(response.status===409)importStatus.textContent='Драфт уже изменился. Дождись обновления.';
  else importStatus.textContent='ПК не принял запрос импорта. Попробуй ещё раз.';
 }catch(_){
  disconnected();
  importStatus.textContent='Не удалось отправить запрос импорта. Повтори после восстановления связи.';
 }finally{
  importing=false;
  syncImport();
  setTimeout(()=>{if(!importing)button.textContent='Импортировать в клиент';},1500);
 }
};
tick()</script></body></html>"""


def local_ip():
    """Адрес компьютера в домашней сети (на него и заходит телефон)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('192.168.0.1', 9)); ip = s.getsockname()[0]; s.close()   # пакет не отправляется, только выбор интерфейса
        return ip
    except Exception:
        return '127.0.0.1'


class PhoneServer:
    def __init__(self, port, on_import, token=None):
        self.state, self.on_import = {'mode': 'idle'}, on_import
        self.token = token or secrets.token_urlsafe(6)
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _ok(self, body, ctype):
                b = body.encode('utf-8')
                self.send_response(200); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b)))
                self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)

            def do_GET(self):
                base = '/' + srv.token
                if self.path.rstrip('/') == base: return self._ok(PAGE, 'text/html; charset=utf-8')
                if self.path.split('?')[0] == base + '/state.json': return self._ok(json.dumps(srv.state, ensure_ascii=False), 'application/json')
                self.send_error(404)

            def do_POST(self):
                if self.path == '/' + srv.token + '/import':
                    state = srv.state
                    if state.get('mode') != 'draft' or not state.get('me'):
                        return self.send_error(409)
                    srv.on_import(); return self._ok('{}', 'application/json')
                self.send_error(404)

        self.httpd = ThreadingHTTPServer(('0.0.0.0', port), H)
        self.url = f'http://{local_ip()}:{port}/{self.token}'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        try: self.httpd.shutdown(); self.httpd.server_close()
        except Exception: pass
