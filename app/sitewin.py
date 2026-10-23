# Сайт со статистикой в окне программы (WebView2 через pywebview). Запускается отдельным процессом: LoLHelper.exe --site.
# Страница и данные берутся с raw.githubusercontent.com: GitHub Pages открывается не у всех.
import os, urllib.request

RAW = 'https://raw.githubusercontent.com/Halches/Lol-stat/main/'
# Страница грузит data/*.json относительными ссылками — направляем их на raw. Свежие игры (live.json) тоже разрешаем.
PATCH = ("<script>(function(){var f=window.fetch;window.fetch=function(u,o){if(typeof u==='string'&&u.indexOf('data/')===0)u='"
         + RAW + "'+u;return f.call(window,u,o)}})()</script>")


def page(home):
    """index.html сайта с подменой ссылок на данные. Нет связи — берём сохранённую в прошлый раз."""
    d = os.path.join(home, 'site')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, 'index.html')
    try:
        req = urllib.request.Request(RAW + 'index.html', headers={'User-Agent': 'LoLHelper'})
        with urllib.request.urlopen(req, timeout=20) as r: html = r.read().decode('utf-8')
        html = html.replace('<head>', '<head>' + PATCH, 1).replace("if(!/github\\.io/.test(location.host))return;", '')
        with open(path + '.tmp', 'w', encoding='utf-8') as f: f.write(html)
        os.replace(path + '.tmp', path)
    except Exception as e:
        print('site', e)
    return path if os.path.exists(path) else None


def run(home):
    import webview
    p = page(home)
    if p:
        webview.create_window('LoL Stat — статистика', url=p, width=1440, height=920, background_color='#010a13')
    else:
        webview.create_window('LoL Stat', html='<body style="background:#010a13;color:#c8aa6e;font:18px Segoe UI;padding:40px">'
                                               'Нет связи с raw.githubusercontent.com. Проверь интернет или VPN и открой снова.</body>')
    webview.start(gui='edgechromium', http_server=True, private_mode=False, storage_path=os.path.join(home, 'site', 'webview'))
