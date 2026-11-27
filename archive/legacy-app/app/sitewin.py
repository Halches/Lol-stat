# Сайт со статистикой в окне программы (WebView2 через pywebview). Запускается отдельным процессом: LoLHelper.exe --site.
# Страница и данные берутся с raw.githubusercontent.com: GitHub Pages открывается не у всех.
import os, re, urllib.request

RAW = 'https://raw.githubusercontent.com/Halches/Lol-stat/main/'
# Страница грузит data/*.json относительными ссылками — направляем их на raw, мимо кеша браузера. Свежие игры (live.json) тоже разрешаем.
PATCH = ("<script>(function(){var f=window.fetch;window.fetch=function(u,o){if(typeof u==='string'&&u.indexOf('data/')===0){"
         "u='" + RAW + "'+u+(u.indexOf('?')<0?'?':'&')+'t='+Math.floor(Date.now()/60000);o=Object.assign({cache:'no-store'},o||{})}"
         "return f.call(window,u,o)}})()</script>")
# Кнопка «Обновить»: программа заново скачивает страницу и перезагружает окно.
BUTTON = ("<button id=lh-refresh title='Скачать свежую версию сайта и игр' onclick=\"this.textContent='Обновляю…';"
          "(window.pywebview&&window.pywebview.api?window.pywebview.api.refresh():Promise.resolve()).then(function(){location.reload()})\" "
          "style='position:fixed;right:14px;bottom:14px;z-index:99999;padding:8px 14px;border-radius:6px;border:1px solid #c8aa6e;"
          "background:#0a1428;color:#c8aa6e;font:600 13px Segoe UI,sans-serif;cursor:pointer;box-shadow:0 2px 8px #0008'>⟳ Обновить</button>")


def page(home):
    """index.html сайта с подменой ссылок на данные и кнопкой «Обновить». Нет связи — берём сохранённую в прошлый раз."""
    d = os.path.join(home, 'site')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, 'index.html')
    try:
        req = urllib.request.Request(RAW + 'index.html', headers={'User-Agent': 'LoLHelper', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, timeout=20) as r: html = r.read().decode('utf-8')
        html = html.replace('<head>', '<head>' + PATCH, 1).replace("if(!/github\\.io/.test(location.host))return;", '')
        html = html.replace('</body>', BUTTON + '</body>', 1)
        with open(path + '.tmp', 'w', encoding='utf-8') as f: f.write(html)
        os.replace(path + '.tmp', path)
    except Exception as e:
        print('site', e)
    return path if os.path.exists(path) else None


class Api:
    """Вызывается со страницы: window.pywebview.api.refresh()."""
    def __init__(self, home): self.home = home

    def refresh(self):
        page(self.home)
        return True


def run(home, game=None):
    import webview
    p = page(home)
    if p and game and re.fullmatch(r'EUW1_\d+', game):   # открыть сразу на этой игре (сайт читает #g-… после загрузки данных)
        html = open(p, encoding='utf-8').read().replace('<head>', f"<head><script>if(!location.hash)location.hash='#g-{game}'</script>", 1)
        p = os.path.join(os.path.dirname(p), 'game.html')
        with open(p, 'w', encoding='utf-8') as f: f.write(html)
    if p:
        webview.create_window('LoL Stat — статистика', url=p, width=1440, height=920, background_color='#010a13', js_api=Api(home))
    else:
        webview.create_window('LoL Stat', html='<body style="background:#010a13;color:#c8aa6e;font:18px Segoe UI;padding:40px">'
                                               'Нет связи с raw.githubusercontent.com. Проверь интернет или VPN и открой снова.</body>')
    webview.start(gui='edgechromium', http_server=True, private_mode=False, storage_path=os.path.join(home, 'site', 'webview'))
