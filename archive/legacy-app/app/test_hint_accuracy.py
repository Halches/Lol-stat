"""Regression cases from the 2026 hint audit; factual inputs, no game or network."""
import copy
import unittest
from unittest.mock import Mock
import core
from test_core import D,snap

class HintAccuracyTests(unittest.TestCase):
    def game(self,t,**kwargs):return core.Game(snap(t,**kwargs),D)
    def dragon_events(self,killers):return [{'EventName':'DragonKill','EventTime':400+i*310,'DragonType':'Fire','KillerName':name} for i,name in enumerate(killers)]
    def test_two_drakes_each_is_not_a_soul(self):
        g=self.game(2000,events=self.dragon_events(['Halch','E1','Halch','E1']))
        self.assertEqual(g.objectives()['dragon_name'],'Дракон');self.assertEqual(g.objectives()['dragon'],1630)
    def test_four_for_one_team_switch_to_elder(self):
        g=self.game(2000,events=self.dragon_events(['Halch']*4))
        self.assertEqual(g.objectives()['dragon_name'],'Древний дракон');self.assertEqual(g.objectives()['dragon'],1690)
    def test_unknown_killers_do_not_fabricate_soul(self):
        g=self.game(2000,events=self.dragon_events(['unknown']*4));self.assertIsNone(g.objectives()['dragon'])
    def test_known_elder_kill_confirms_elder_respawn(self):
        g=self.game(2000,events=[{'EventName':'DragonKill','EventTime':1800,'DragonType':'Elder'}]);self.assertEqual(g.objectives()['dragon'],2160)
    def test_full_riot_id_not_just_game_name(self):
        raw=snap(100);raw['allPlayers'].insert(0,dict(copy.deepcopy(raw['allPlayers'][0]),riotId='Halch#OTHER',team='CHAOS'))
        g=core.Game(raw,D);self.assertEqual(g.me['riot'],'Halch#EUW');self.assertIsNone(g.by_name('Halch'));self.assertEqual(g.by_name('Halch#OTHER')['team'],'CHAOS')
    def test_missing_active_identity_is_not_first_player(self):
        raw=snap(100);raw['activePlayer']={'currentGold':500};g=core.Game(raw,D)
        self.assertIsNone(g.me);self.assertEqual(core.Engine(D,None).tick(g),[])
    def test_missing_jungler_does_not_consume_intro(self):
        eng=core.Engine(D,None);raw=snap(4);raw['allPlayers'][6]['position']='';raw['allPlayers'][6]['summonerSpells']={}
        g=core.Game(raw,D);self.assertIsNone(g.ejg);eng.tick(g)
        self.assertIn('jungler',[h.id for h in eng.tick(self.game(5))])
    def test_objective_survives_a_short_poll_gap_and_uses_remaining_time(self):
        eng=core.Engine(D,None);eng.tick(self.game(236));hints=eng.tick(self.game(244))
        hint=next(h for h in hints if h.id=='objectives' and 'Дракон' in h.text)
        self.assertIn('56 с',hint.text);self.assertNotIn('60 с',hint.text)
        self.assertFalse(any(h.id=='objectives' and 'Дракон' in h.text for h in eng.tick(self.game(245))))
    def test_old_threshold_not_replayed_on_late_connection(self):
        self.assertFalse(any(h.id=='bench' for h in core.Engine(D,None).tick(self.game(1200))))
    def test_missing_vision_is_not_zero(self):
        raw=snap(600);del raw['allPlayers'][0]['scores']['wardScore']
        hints=core.Engine(D,None).tick(core.Game(raw,D));self.assertNotIn('vision',[h.id for h in hints])
        self.assertIn('vision',[h.id for h in core.Engine(D,None).tick(self.game(600))])
    def test_dead_player_not_told_to_recall_with_hoarded_gold(self):
        g=self.game(600,gold=2500);g.me['dead']=True
        self.assertNotIn('hoard',[h.id for h in core.Engine(D,None).tick(g)])
    def test_fiddlesticks_effigy_is_a_trinket(self):
        self.assertNotIn('trinket',[h.id for h in core.Engine(D,None).tick(self.game(40,me={'items':[3330]}))])
    def test_skill_hint_not_sent_after_point_spent(self):
        raw=snap(100,me={'lvl':3});raw['activePlayer']['abilities']={k:{'abilityLevel':1 if k!='R' else 0} for k in 'QWER'}
        eng=core.Engine(D,None);eng.skills='QWEQQRQWQWRWWEEREE'
        self.assertNotIn('skills',[h.id for h in eng.tick(core.Game(raw,D))])
    def test_late_connection_does_not_replay_old_skill_levels(self):
        eng=core.Engine(D,None);eng.skills='QWEQQRQWQWRWWEEREE'
        self.assertNotIn('skills',[h.id for h in eng.tick(self.game(1000,me={'lvl':12}))])
    def test_other_map_gets_no_sr_timers_or_hints(self):
        raw=snap(240);raw['gameData'].update(gameMode='ARAM',mapNumber=12);g=core.Game(raw,D)
        self.assertEqual(g.objectives(),{});self.assertIsNone(g.next_cannon());self.assertEqual(core.Engine(D,None).tick(g),[])
    def test_late_cannon_schedule_is_not_guessed(self):
        self.assertEqual(self.game(61).next_cannon(),90);self.assertIsNone(self.game(840).next_cannon());self.assertIsNone(self.game(1800).next_cannon())
    def test_jungler_kill_does_not_prove_map_position(self):
        event={'EventName':'ChampionKill','EventTime':398,'KillerName':'E2','VictimName':'A4','Assisters':[]}
        hint=next(h for h in core.Engine(D,None).tick(self.game(400,events=[event])) if h.id=='jg_seen')
        self.assertIn('не подтверждено',hint.text);self.assertNotIn('можно давить',hint.text)
    def test_future_kill_not_counted_as_current_activity(self):
        event={'EventName':'ChampionKill','EventTime':410,'KillerName':'E2','VictimName':'A4','Assisters':[]}
        self.assertNotIn('jg_seen',[h.id for h in core.Engine(D,None).tick(self.game(400,events=[event]))])
    def test_side_lane_does_not_invent_personal_death_statistics(self):
        hint=next(h for h in core.Engine(D,None).tick(self.game(1000,me={'items':[3071]})) if h.id=='side_lane')
        self.assertNotIn('в твоих играх',hint.text);self.assertIn('не гарантирует',hint.text)
    def test_team_lead_is_explicitly_inventory_value(self):
        hint=next(h for h in core.Engine(D,None).tick(self.game(1000,me={'items':[3071,3031]})) if h.id=='team_gold')
        self.assertIn('стоимости предметов',hint.text)
    def test_full_inventory_does_not_prompt_control_ward(self):
        eng=core.Engine(D,None);eng.tick(self.game(400,gold=2000))
        hints=eng.tick(self.game(401,gold=200,me={'items':[1001,1036,1055,1028,1033,1057]}));self.assertNotIn('control',[h.id for h in hints])
    def test_disabled_cooldown_does_not_delay_enabling(self):
        flags={h:True for h in core.HINT_IDS};flags['hoard']=False;eng=core.Engine(D,None,enabled=flags)
        eng.tick(self.game(600,gold=2500));flags['hoard']=True
        self.assertIn('hoard',[h.id for h in eng.tick(self.game(601,gold=2500))])
    def test_champion_norm_not_borrowed_from_other_champions(self):
        player=Mock();player.on.return_value=[{'opp':'Darius','w':1,'g15':None}]
        core.Engine(D,player).tick(self.game(300));player.norm.assert_not_called()
    def test_teleport_is_a_check_not_claim_of_readiness(self):
        eng=core.Engine(D,None);eng.tick(self.game(239));hints=eng.tick(self.game(240))
        hint=next(h for h in hints if h.id=='tp');self.assertIn('Перезарядка не известна',hint.text)

    def support(self,t,items,level=5,gold=200):
        raw=snap(t,me={'items':items,'lvl':level},gold=gold);raw['allPlayers'][0]['position']='UTILITY'
        return core.Game(raw,D)
    def test_lens_follows_ward_item_not_level_nine(self):
        hints=core.Engine(D,None).tick(self.support(400,[3340,3866],level=5))
        self.assertIn('lens',[h.id for h in hints])
    def test_level_nine_without_ward_item_does_not_trigger_lens(self):
        self.assertNotIn('lens',[h.id for h in core.Engine(D,None).tick(self.support(400,[3340,3865],level=9))])
    def test_support_quest_control_discount_and_separate_slot(self):
        eng=core.Engine(D,None);eng.tick(self.support(400,[3869],gold=1000))
        hints=eng.tick(self.support(401,[3869,1001,1036,1055,1028,1033],gold=50))
        hint=next(h for h in hints if h.id=='control');self.assertIn('не подтверждено',hint.text)

    def test_stored_profile_matching_never_ignores_supplied_tag(self):
        data=core.Data({**D.d,'players':{'one':{'riot':'Same#A'},'two':{'riot':'Same#B'}}})
        self.assertEqual(data.who_by_riot('Same#A'),'one');self.assertIsNone(data.who_by_riot('Same#C'))
        self.assertIsNone(data.who_by_riot('Same'));self.assertIsNone(data.who_by_riot(''))

    def test_full_game_cs_not_divided_by_invented_28_minutes(self):
        eng=core.Engine(D,None);eng.bench={'cs':210,'min':28}
        hint=next(h for h in eng.tick(self.game(600)) if h.id=='bench');self.assertNotIn('Изумруд+',hint.text)
    def test_verified_cs_per_minute_can_be_used(self):
        eng=core.Engine(D,None);eng.bench={'csm':7}
        hint=next(h for h in eng.tick(self.game(600)) if h.id=='bench');self.assertIn('Изумруд+ ~70',hint.text)

if __name__=='__main__':unittest.main()
