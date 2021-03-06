from game import DartGame

from circuits import Component, Event, Debugger, handler, reprhandler

from events import *
from components.webserver import DartsWebServer
from components.logger import Logger, DetailedLogger
from components.input import DartInput, FileInput
from components.legacysounds import LegacySounds
from components.espeaksounds import EspeakSounds
from components.isatsounds import ISATSounds

from subprocess import Popen, PIPE

import unittest


class MyTestDebugger(Component):

    test_result = None
    test_final_state = None

    @handler("error", channel="*", priority=100.0)
    def _on_error(self, error_type, value, traceback, handler=None, fevent=None):
        s = []

        if handler is None:
            handler = ""
        else:
            handler = reprhandler(handler)

        msg = "ERROR %s (%s) {%s}: %s\n" % (handler, fevent, error_type, value)
        s.append(msg)
        s.extend(traceback)
        s.append("\n")
        self.test_result = "".join(s)
        self.test_result = False
        print 'Stopping - error.'
        self.root.stop()

    def GameOver(self, state):
        self.test_result = True
        self.test_final_state = state
        print 'Stopping - game is over.'
        self.root.stop()

class TestFullGame(unittest.TestCase):
    TESTFILE = 'test/testgames/T1-T2-T3.dartlog'
    def component(self, comp):
        dbg = MyTestDebugger() 
        comp += dbg
        comp.run()
        self.assertEquals(dbg.test_result, True)
        res = [(x['name'], x['rank'], x['score']) for x in dbg.test_final_state.player_list()]
        exp_res = [('T2', 2, 1), ('T1', 1, 0), ('T3', 0, 0)]
        self.assertEquals(res, exp_res)

    def test_a(self):
        comp = DartGame()\
            + FileInput(self.TESTFILE, delay=0.5)
        self.component(comp)
            
    def test_b(self):
        dl = DetailedLogger(test=True)
        comp = DartGame() + FileInput(self.TESTFILE, delay=0.5) \
               + Logger()\
               + EspeakSounds(test=True)\
               + ISATSounds(test=True)\
               + LegacySounds(test=True)\
               + dl + Debugger()\
               + DartsWebServer()
        self.component(comp)

        # check to see if the detailed logger worked
        num_games, num_throws = dl.get_num_rows()
        self.assertEquals(num_games, 1)
        self.assertEquals(num_throws, 25)

    def test_run(self):
        p = Popen(['./game.py', '--dev', 'none', '--file', self.TESTFILE, '--nolog', '--test', '--one-game', '--snd', 'none'], stdout=PIPE, stderr=PIPE)
        d = p.communicate()
        rank = '''Ranking:
1: T3
2: T1
3: T2'''
        self.assertIn(rank, d[0])
        self.assertEquals(d[1], '')
        self.assertEquals(p.returncode, 0)
        
