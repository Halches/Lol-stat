import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from qt_app import App
from lcu import LCU


class PostgameMatchTests(unittest.TestCase):
    def test_gameflow_match_id(self):
        client = LCU()
        for phase, match_id, expected in [('InProgress', 102, 102), ('Lobby', 101, None), ('Reconnect', 0, None)]:
            with patch.object(client, 'call', return_value={'phase': phase, 'gameData': {'gameId': match_id}}):
                self.assertEqual(client.live_match_id(), expected)

    def test_wait_for_this_match_then_for_timeline(self):
        callbacks = []
        client = Mock()
        current = {'gameId': 102, 'participantIdentities': [{'participantId': 1, 'player': {'puuid': 'player'}}],
                   'participants': [{'participantId': 1, 'championId': 105}]}
        client.game.side_effect = [dict(current, gameId=101), None, current, current, current]
        client.timeline.side_effect = [None, {'frames': []}, {'frames': [{'events': []}]}]
        app = SimpleNamespace(client=client, account={'puuid': 'player'}, offline=False, stopping=Mock(),
                              cid=lambda champ: 105, root=SimpleNamespace(after=lambda ms, cb: callbacks.append(cb)),
                              background=lambda work, done: done(work(), None))
        app.stopping.is_set.return_value = False
        dialog, body = Mock(), Mock()
        with (patch('qt_app.isValid', return_value=True), patch('qt_app.Label') as note,
              patch('qt_app.QLabel'), patch('qt_app.pixmap'), patch('qt_app.render.death_map') as draw):
            App.postgame_timeline(app, body, {'match_id': 102, 'me': {'c': 'Fizz'}}, dialog)
            for _ in range(4):
                callbacks.pop(0)()
                draw.assert_not_called()
            callbacks.pop(0)()
            self.assertEqual(draw.call_args.args[0], [])
            self.assertIn('не было', note.return_value.setText.call_args.args[0])
        client.history.assert_not_called()
        self.assertEqual([c.args for c in client.game.call_args_list], [(102,)] * 5)
        self.assertEqual([c.args for c in client.timeline.call_args_list], [(102,)] * 3)
        self.assertEqual(callbacks, [])
