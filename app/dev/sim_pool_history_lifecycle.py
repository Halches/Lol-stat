"""Real pool interactions and full saved-match display, without a running client."""
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lcu
import lolhelper
import ui
import history_model


def main():
    with tempfile.TemporaryDirectory(prefix='lol-pool-history-') as folder:
        ui.app_home=lambda:folder
        Path(folder,'settings.json').write_text(json.dumps({'design3':True,'dashboard':False,'sound':'off'}),encoding='utf-8')
        for name in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon','sync_phone'):
            setattr(ui.App,name,lambda *a,**k:None)
        ui.Voice.warm=lambda *a:None;lcu.LCU.image=lambda *a:None
        calls=[]
        def unexpected_game(*args):calls.append(args);raise AssertionError('saved match attempted an LCU request')
        lcu.LCU.game=unexpected_game
        app=ui.App(lolhelper.load_data(),'POOL AND SAVED HISTORY CHECK')
        app.root.geometry('1060x740+0+0');app.nb.select(10)
        view=app.pool_view;errors=[];checks=[];timings=[];cards={};popup=None;player_cards=[]
        def fail(message):errors.append(message);app.root.destroy()
        app.root.report_callback_exception=lambda et,ev,tb:fail(repr(ev))
        def step(func):
            def run():
                try:func()
                except Exception as error:fail(repr(error))
            return run
        def start():
            nonlocal cards
            cards=dict(view.cards);initial=app.current_pool()
            for _ in range(10):
                before=time.perf_counter();view.cards['Ahri'].event_generate('<Button-1>');timings.append((time.perf_counter()-before)*1000)
                assert all(view.cards[key] is card for key,card in cards.items())
            assert app.current_pool()==initial
            view.cv.yview_moveto(.5)
            for _ in range(15):view.cv.wheel(type('Wheel',(),{'delta':-120})())
            app.root.after(120,step(filtered))
        def filtered():
            assert all(view.cards[key] is card for key,card in cards.items())
            checks.append('pool clicks and scroll preserve card widgets')
            view.choose_mode('pool');view.choose_mode('all');view.choose_role('TOP');view.choose_role('MIDDLE')
            assert all(view.cards[key] is card for key,card in cards.items())
            checks.append('pool filters and role changes reuse card widgets')
            app.root.geometry('1300x840+0+0');app.root.after(160,step(open_match))
        def open_match():
            nonlocal popup
            assert all(view.cards[key] is card for key,card in cards.items())
            records=history_model.saved(app.player.games,app.data,app.who)
            record=next(row for row in records if row.get('match_id') in app.data.d.get('match_details',{}))
            popup=app.history_view.open_record(record)
            app.root.after(200,step(detail))
        def detail():
            nonlocal player_cards
            assert popup.review and len(popup.review['rows'])==10
            assert popup.review['me'] and popup.review['me']['dmg'] is not None
            assert len(popup.player_cards)==10
            assert not calls
            player_cards=list(popup.player_cards);popup.cv.yview_moveto(.5)
            app.root.after(120,step(finish))
        def finish():
            assert popup.player_cards==player_cards,'scroll rebuilt match details'
            checks.append('saved match displays ten real participants without LCU')
            popup.close();app.root.destroy()
        app.root.after(600,step(start));app.root.after(20000,lambda:fail('pool/history test timeout'))
        app.run()
        report={'platform':sys.platform,'errors':errors,'checks':checks,'pool_cached_cards':len(cards),
            'saved_archive_matches':len(app.data.d.get('match_details',{})),
            'pool_toggle_median_ms':round(statistics.median(timings),2) if timings else None,
            'pool_toggle_max_ms':round(max(timings),2) if timings else None}
        output=Path(os.environ.get('POOL_HISTORY_CHECKS_OUT','/tmp/pool-history-checks.json'))
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
        if errors or len(checks)!=3:raise SystemExit(1)


if __name__=='__main__':main()
