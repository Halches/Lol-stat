# Главное окно: python3.12 sim_main.py <номер вкладки> [файл.png] -> скриншот 1060x740.
import sys, subprocess
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import lcu, ui, lolhelper
lcu.live_data = lambda: None
ui.App.poll = lambda self: None
app = ui.App(lolhelper.load_data(), 'v1.0.22', lolhelper.updater)
tab = int(sys.argv[1]) if len(sys.argv) > 1 else 0
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get('SIM_OUT', '/tmp'), 'm_home.png')
def go():
    if app.dash: app.dash.withdraw()
    app.root.geometry('1060x740+0+0'); app.nb.select(tab)
app.root.after(1000, go)
app.root.after(2500, lambda: subprocess.run(['import', '-window', 'root', '-crop', '1060x740+0+0', out]))
app.root.after(3000, app.root.destroy)
app.run()
