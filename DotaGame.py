import W3Game
import json

UNIT_DATA = json.loads(open("units.json").read())

class Player:
    def __init__(self, id, name, slot):
        self.id = id
        self.name = name
        self.hero = ""
        self.kills = 0
        self.assists = 0
        self.deaths = 0
        self.ckills = 0
        self.cdenies = 0
        self.cneutrals = 0
        self.level = 0
        self.gold = 0
        self.slot = slot
        self.color = slot['color']
        self.dota_id = self.get_dota_id()

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
    def __init__(self, player, message, mode):
        self.player = player
        self.message = message
        self.mode = mode

    def __repr__(self):
        return "<Message>"

class DotaGame:
    def __init__(self, replay):
        self.replay = replay
        self.data = W3Game.W3Game(replay).parse()

        self.gamename = self.data['gameinfo']['gamename']

        self.players = []
        for player in self.data['gameinfo']['players']:
            plr = Player(player['id'], player['name'], player['slot'])
            self.players.append(plr)
        
        self.messages = []
        for gd in self.data['gamedata']:
            if not isinstance(gd, dict) or gd['type'] != "CHATMESSAGE":
                continue
            self.messages.append(Message(self.get_player(gd['data']['player_id']), gd['data']['message'], gd['data']['mode']))

        for player in self.players:
            print player._get_id()
        self.parse_dotainfo()

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
        info = dict()
        for gd in self.data['gamedata']:
            if not isinstance(gd, dict) or gd['type'] != "TIMESLOT":
                continue
            for command_block in gd['data']['command_blocks']:
                for action in command_block['actions']:
                    if not isinstance(action, dict) or action['name'] != "DotaInfo":
                        continue
                    a, b, c = action['data']['strings']

                    if a.isdigit():
                        player_id = int(a)
                        data = c
                        act = ''

                        if b == '1':
                            act = 'kills'
                            print "KILLS:", player_id
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

                        if not info.has_key(player_id):
                            info[player_id] = dict()
                        info[player_id][act] = data

        for player in self.players:
            player.kills = info[player.dota_id]['kills']
            player.deaths = info[player.dota_id]['deaths']
            player.assists = info[player.dota_id]['assists']
            player.ckills = info[player.dota_id]['ckills']
            player.cdenies = info[player.dota_id]['cdenies']
            player.cneutrals = info[player.dota_id]['cneutrals']
            player.hero = Hero(info[player.dota_id]['hero'])
