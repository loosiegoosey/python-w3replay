import W3Game
import json
import util
from collections import defaultdict

UNIT_DATA = json.loads(open("units.json").read())

class Player:
    def __init__(self, id, name, slot):
        self.id = id
        self.name = name
        self.hero = ""
        self.kills = 0
        self.assists = 0
        self.deaths = 0
        self.towers = 0
        self.ckills = 0
        self.cdenies = 0
        self.cneutrals = 0
        self.level = 0
        self.gold = 0
        self.slot = slot
        self.color = slot['color']
        self.dota_id = self.get_dota_id()
        self.messages = []
        self.kill_log = []
        self.death_log = []
        self.assist_log = []
        self.tower_log = []

    def get_dota_id(self):
        return self.color

    def __repr__(self):
        return "<Player '(%s) %s'>" % (self.id, self.name)

class Hero:
    def __init__(self, id):
        self.id = id
        if not UNIT_DATA.has_key(self.id):
            self.name = "UNKOWN"
            self.icon = "unkown.png"
        else:
            self.name = UNIT_DATA[self.id]['ProperNames'][0]
            self.icon = UNIT_DATA[self.id]['Image'][:-4] + ".png"

    def __repr__(self):
        return "<Hero '%s' (%s)>" % (self.id, self.name)

class Message:
    def __init__(self, player, text, mode, time):
        self.player = player
        self.text = text
        self.mode = mode
        self.time = time

    def __repr__(self):
        return "<Message>"

class DotaGame:
    def __init__(self, replay):
        self.replay = replay
        self.data = W3Game.W3Game(replay).parse()

        self.gamename = self.data['gameinfo']['gamename']
        self.mode = ""

        self.players = []
        for player in self.data['gameinfo']['players']:
            plr = Player(player['id'], player['name'], player['slot'])
            self.players.append(plr)
        
        self.messages = []
        for gd in self.data['gamedata']:
            if not isinstance(gd, dict) or gd['type'] != "CHATMESSAGE":
                continue
            message = Message(self.get_player(gd['data']['player_id']), gd['data']['message'], gd['data']['mode'], gd['time'])
            self.messages.append(message)
            message.player.messages.append(message)

        self.parse_dotainfo()

    def get_dotaplayer(self, pid):
        for player in self.players:
            if player.dota_id == pid:
                return player

    def get_player(self, pid):
        for player in self.players:
            if player.id == pid:
                return player
        return

    def find_player(self, s):
        for player in self.players:
            if player.name.lower() == s.lower():
                return player

    def parse_dotainfo(self):
        # TODO: Parse timed actions and inventory/abilities.
        info = defaultdict(lambda: defaultdict(list))
        for gd in self.data['gamedata']:
            if not isinstance(gd, dict) or gd['type'] != "TIMESLOT":
                continue
            for command_block in gd['data']['command_blocks']:
                for action in command_block['actions']:
                    if not isinstance(action, dict) or action['name'] != "DotaInfo":
                        continue
                    a, b, c = action['data']['strings']

                    if a == 'Data':
                        if b.startswith('Mode'):
                            data = b.replace('Mode', '')
                            self.mode = data
                        elif b.startswith('Hero'):
                            data = b.replace('Hero', '')
                            player_id = int(c)
                            victim_id = int(data)
                            info[player_id]['kill_log'].append({'time': gd['time'], 'victim': self.get_dotaplayer(victim_id)})
                            info[victim_id]['death_log'].append({'time': gd['time'], 'killer': self.get_dotaplayer(player_id)})
                        elif b.startswith('Assist'):
                            data = b.replace('Assist', '')
                            player_id = int(data)
                            victim_id = int(c)
                            info[player_id]['assist_log'].append({'time': gd['time'], 'victim': self.get_dotaplayer(victim_id)})
                        elif b.startswith('Level'):
                            data = b.replace('Level', '')
                        elif b.startswith('PUI_'):
                            data = b.replace('PUI_', '')
                        elif b.startswith('DRI_'):
                            data = b.replace('DRI_', '')
                        elif b.startswith('Tower'):
                            # TODO: Read Team/Lane/Number information from tower (b=Team(0/1)/Number(1/2/3/4)/Lane(0/1/2))
                            player_id = int(c)
                            if not info[player_id]['towers']:
                                info[player_id]['towers'] = 0
                            info[player_id]['towers'] += 1
                            info[player_id]['tower_log'].append({'time': gd['time']})

                    elif a.isdigit():
                        player_id = int(a)
                        data = c
                        act = ''

                        if b == '1':
                            act = 'kills'
                        elif b == '2':
                            act = 'deaths'
                        elif b == '3':
                            act = 'ckills'
                        elif b == '4':
                            act = 'cdenies'
                        elif b == '5':
                            act = 'assists'
                        elif b == '6':
                            act = 'gold'
                        elif b == '7':
                            act = 'cneutrals'
                        elif b == '8':
                            act = 'inventory'
                        elif b == '9':
                            act = 'hero'
                        elif b == 'id':
                            continue

                        info[player_id][act] = data

        for player in self.players:
            player.kills = info[player.dota_id]['kills']
            player.deaths = info[player.dota_id]['deaths']
            player.assists = info[player.dota_id]['assists']
            player.towers = info[player.dota_id]['towers']
            player.ckills = info[player.dota_id]['ckills']
            player.cdenies = info[player.dota_id]['cdenies']
            player.cneutrals = info[player.dota_id]['cneutrals']
            player.gold = info[player.dota_id]['gold']
            player.hero = Hero(info[player.dota_id]['hero'])
            player.kill_log = info[player.dota_id]['kill_log']
            player.death_log = info[player.dota_id]['death_log']
            player.assist_log = info[player.dota_id]['assist_log']
            player.tower_log = info[player.dota_id]['tower_log']
            
            # correct zero towers
            if player.towers == []:
                player.towers = 0

DotaGame("/home/mephory/g.w3g")
