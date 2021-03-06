""" Websockets connector """

from circuits import Component, Event, handler
from circuits.web.dispatchers import WebSockets
from circuits.web import Server, Controller, Logger, Static
from circuits.net.sockets import write, connect
from circuits.web.tools import check_auth, basic_auth
from random import random
from base64 import b64decode
 
import simplejson

from events import *

try:
    from settings import users
except ImportError:
    users = {"pidart": "pidart"}

try:
    from settings import port
except ImportError:
    port = 8080

try:
    from settings import listen
except ImportError:
    listen = '0.0.0.0'


class SendState(Event):
    pass

class SendInfo(Event):
    pass

class SendSettings(Event):
    pass


def sanitize_input_dart(dart):
    inner = False
    if dart[-1] == 'i':
        inner = True
        dart = dart[:-1]
    dart = dart.upper()
    # the following fails if len(dart) == 0:
    if (dart[0] not in ['S', 'D', 'T']):
        dart = 'S%s' % dart
    # fails if dart not numeric:
    if not 1 <= int(dart[1:]) <= 20:
        raise ValueError("Dart's value should be above 0 and below 21.")
    if inner and dart[0] == 'S':
        dart = "%si" % dart
    return dart

class DartsWSServer(Component):
    channel = "wsserver"

    def __init__(self):
        Component.__init__(self)
        self.connectState = {
            'state': 'null', 
            'players': [], 
            'ranking': []
        }
        self.connectSettings = {}
        self.knownSockets = []  
        self.random_id = random()

    def read(self, sock, data):
        if data == 'hello':
            self.send_json({
                'type': 'version',
                'version': self.random_id
            }, sock)
            self.send_json({
                'type': 'state',
                'state': self.connectState
            }, sock)
            self.send_json({
                'type': 'settings',
                'settings': self.connectSettings
            }, sock)
            self.knownSockets.append(sock)

    def send_json(self, msg, receiver = None):
        msg = simplejson.dumps(msg)
        for s in [receiver] if receiver else self.knownSockets:
            self.fireEvent(write(s, msg))
                
    @handler('SendInfo')
    def SendInfo(self, info):
        self.send_json({
            'type': 'info',
            'info': info
        })

    @handler('SendState', priority=1)
    def SendState(self, state):
        self.send_json({
            'type': 'state',
            'state': state
        })
        self.connectState.update(state)

    @handler('SendSettings')
    def SendSettings(self, settings):
        self.send_json({
            'type': 'settings',
            'settings': settings
        })
        self.connectSettings.update(settings)


class DartsServerController(Component):
    def serialize_short(self, state):
        return {
            'currentPlayer': state.currentPlayer.name,
            'currentDarts': state.currentDarts,
            'currentScore': state.currentPlayer.score - state.currentScore,
            'players': [p.name for p in state.players],
            'state': state.state
            }

    def serialize_full(self, state):
        a = self.serialize_short(state)
        a['ranking'] = state.player_list(sortby = 'started')
        return a

    @handler('GameInitialized', 'FrameFinished', 'FrameStarted', 'GameOver', 'GameStateChanged')
    def _send_full_state(self, state):
        self.fire(SendState(self.serialize_full(state)))

    @handler('GameInitialized')
    def _send_game_initialized(self, state):
        self.fire(SendInfo('game_initialized'))

    @handler('GameOver')
    def _send_game_over(self, state):
        self.fire(SendInfo('game_over'))

    @handler('Hit', 'HitBust', 'HitWinner', priority=1)
    def _send_short_state(self, state, *args):
        self.fire(SendState(self.serialize_short(state)))

    @handler('EnterHold', 'LeaveHold')
    def _send_only_state(self, state, *args):
        self.fire(SendState({'state': state.state}))

    @handler('SettingsChanged')
    def _send_settings(self, settings):
        self.fire(SendSettings(settings))


class Root(Controller):

    def index(self):
        return 

    def xhr(self, *args, **kwargs):
        realm = "pidart"
        encrypt = str

        if not check_auth(self.request, self.response, realm, users, encrypt):
            return basic_auth(self.request, self.response, realm, users, encrypt)

        if self.request.method != 'POST':
            return simplejson.dumps({'error':"Only method POST is allowed."})
            
        data = simplejson.loads(b64decode(self.request.body.read()))
        cmd = data['command']
        if cmd == 'skip-player':
            self.fireEvent(SkipPlayer(int(data['player'])))
        elif cmd == 'new-game':
            players = data['players']
            start = int(data['startvalue'])
            testgame = data['testgame']
            self.fireEvent(StartGame(players, start, testgame))
        elif cmd == 'update-players':
            players = data['players']
            self.fireEvent(UpdatePlayers(players))
        elif cmd == 'change-last-round':
            player = int(data['player'])
            oldDarts = map(sanitize_input_dart, data['old_darts'])
            newDarts = map(sanitize_input_dart, data['new_darts'])
            self.fireEvent(ChangeLastRound(player, oldDarts, newDarts))
        elif cmd == 'apply-settings':
            self.fireEvent(UpdateSettings(data['settings']))
        elif cmd == 'debug-throw-dart':
            dart = sanitize_input_dart(data['dart'])
            self.fireEvent(ReceiveInput('code', dart))
        elif cmd == 'debug-next-player':
            self.fireEvent(ReceiveInput('generic', 'next_player'))
        elif cmd == 'perform-self-update':
            self.fire(PerformSelfUpdate())
        elif cmd == 'cancel-game':
            self.fireEvent(ReceiveInput('generic', 'cancel_game'))
        elif cmd == 'undo-last-frame':
            player = int(data['player'])
            self.fireEvent(UndoLastFrame(player))
        

        return simplejson.dumps({'success': True})

class DartsWebServer(Server):
    def __init__(self):
        Server.__init__(self, (listen, port))
        Static(docroot="../html/").register(self)
        DartsWSServer().register(self)
        DartsServerController().register(self)
        Root().register(self)
        #Logger().register(Webserver)
        WebSockets("/websocket").register(self)
