import sys
from cStringIO import StringIO
import zlib
import struct

def decompress(data):
    dc = zlib.decompressobj(-zlib.MAX_WBITS)
    decomp_data = dc.decompress(data)
    decomp_data += dc.flush()
    return decomp_data

class W3Game:
    def __init__(self, filename):
        self.replayfile = filename
        self.data = open(self.replayfile)
        self.info = {}
        
    def read(self, length):
        if isinstance(length, str):
            fmt = struct.Struct(length)
            return fmt.unpack(self.data.read(fmt.size))
        return self.data.read(length)

    def read_string(self):
        s = ''
        c = self.read(1)
        while c != '\0':
            s += c
            c = self.read(1)
        return s

    def read_header(self):
        keys = "id size compressed_size version decompressed_size num_datablocks w3_version w3_version_number build_number is_multiplayer length checksum".split()
        header = dict(zip(keys, self.read("28sIIIII4sIHHII")))

        # Convert values
        header['is_multiplayer'] = header['is_multiplayer'] != '\0\0' 
        return header

    def read_playerrecord(self):
        player = dict()
        player['record_id'] = self.read(1)
        player['id'] = ord(self.read(1))
        player['name'] = self.read_string()
        gametype = self.read(1)
        if gametype == '\x01':
            self.read(1)
        else:
            self.read(8)
        return player

    def read_slotrecord(self):
        slot = dict()
        slot['player_id'] = ord(self.read(1))
        slot['download_percent'] = self.read(1)
        slot['status'] = self.read(1)
        slot['is_computer'] = self.read(1) == '\x01'
        slot['team'] = ord(self.read(1))
        slot['color'] = ord(self.read(1))
        slot['race'] = self.read(1)
        slot['ai_strength'] = self.read(1)
        slot['handicap'] = self.read(1)
        return slot

    def read_gameinfo(self):
        # TODO: Convert values

        gameinfo = dict()
        gameinfo['host'] = self.read_playerrecord()
        gameinfo['gamename'] = self.read_string()
        # TODO: Decode gamesettings string (see w3g_format.txt)
        self.read(1)
        gamesettings_encoded = self.read_string()

        gameinfo['num_players'] = self.read("I")

        gameinfo['gametype'] = dict()
        gameinfo['gametype']['type'] = self.read(1)
        gameinfo['gametype']['is_private'] = self.read("B") == '0x08'
        self.read("H")

        gameinfo['language'] = self.read("I")

        gameinfo['players'] = list()
        gameinfo['players'].append(gameinfo['host'])
        while self.read(1) == '\x16':
            self.data.seek(self.data.tell() - 1)
            gameinfo['players'].append(self.read_playerrecord())
            self.read("I")
        self.data.seek(self.data.tell() - 1)

        assert self.read(1) == '\x19'
        num_databytes = self.read("H")[0]
        gameinfo['num_slots'] = ord(self.read(1))
        for i in range(gameinfo['num_slots']):
            slot = self.read_slotrecord()
            for player in gameinfo['players']:
                if player['id'] == slot['player_id']:
                    player['slot'] = slot
        gameinfo['random_seed'] = self.read(4)
        gameinfo['select_mode'] = self.read(1)
        gameinfo['num_startspots'] = ord(self.read(1))
        return gameinfo

    def parse(self):
        self.info['header'] = self.read_header()

        io = StringIO()
        for i in range(self.info['header']['num_datablocks']):
            compressed_size, decompressed_size, checksum = self.read("HHI")
            io.write(decompress(self.read(compressed_size)[2:]))
        io.seek(4)
        self.data = io

        self.info['gameinfo'] = self.read_gameinfo()

        data_reader = ReplayDataReader(self.data)

        self.info['gamedata'] = data_reader.parse()

        return self.info

class ReplayDataReader:
    def __init__(self, data):
        self.data = data
        self.blocks = {'\x17': ('LeaveGame',   self.handleLeaveGame),
                       '\x1A': ('Unkown',      self.skip(4)),
                       '\x1B': ('Unkown',      self.skip(4)), 
                       '\x1C': ('Unkown',      self.skip(4)), 
                       '\x1E': ('TimeSlotOld', self.handleTimeSlot), 
                       '\x1F': ('TimeSlot',    self.handleTimeSlot), 
                       '\x20': ('ChatMessage', self.handleChatMessage), 
                       '\x22': ('Checksum',    self.skip(5)), 
                       '\x23': ('Unkown',      self.skip(10)), 
                       '\x2F': ('ForceGameEnd',self.handleForceGameEnd)}

        self.action_blocks = {'\x01': ('PauseGame',    self.handlePauseGame), 
                               '\x02': ('ResumeGame',   self.handleResumeGame), 
                               '\x03': ('SetGamespeed', self.handleSetGamespeed), 
                               '\x04': ('IncrGamespeed',self.handleIncrGamespeed), 
                               '\x05': ('DecrGamespeed',self.handleDecrGamespeed), 
                               '\x06': ('SaveGame',     self.handleSaveGame),
                               '\x07': ('SaveGameFinished', self.handleSaveGameFinished),
                               '\x10': ('UnitAbility',  self.handleUnitAbility),
                               '\x11': ('UnitAbilityTargetPos', self.handleUnitAbilityTargetPos),
                               '\x12': ('UnitAbilityTargetPosObj', self.handleUnitAbilityTargetPosObj),
                               '\x13': ('DropItem',     self.handleDropItem),
                               '\x14': ('UnitAbilityTargetTwoPosObj', self.handleUnitAbilityTargetTwoPosObj),
                               '\x16': ('ChangeSelection', self.handleChangeSelection),
                               '\x17': ('AssignGroupHotkey', self.handleAssignGroupHotkey),
                               '\x18': ('SelectGroupHotkey', self.handleSelectGroupHotkey),
                               '\x19': ('SelectSubgroup', self.handleSelectSubgroup),
                               '\x1A': ('UpdateSubgroup', self.handleUpdateSubgroup),
                               '\x1B': ('Unknown',       self.skip(9)),
                               '\x1C': ('SelectGroundItem', self.handleSelectGroundItem),
                               '\x1D': ('CancelHeroRevival', self.handleCancelHeroRevival),
                               '\x1E': ('RemoveUnitFromBuildingQueue', self.handleRemoveUnitFromBuildingQueue),
                               '\x21': ('Unknown',      self.skip(8)),
                               '\x20': ('Cheat1',       self.skip(0)),
                               '\x22': ('Cheat2',       self.skip(0)),
                               '\x23': ('Cheat3',       self.skip(0)),
                               '\x24': ('Cheat4',       self.skip(0)),
                               '\x25': ('Cheat5',       self.skip(0)), 
                               '\x26': ('Cheat6',       self.skip(0)), 
                               '\x27': ('Cheat7',       self.skip(5)),
                               '\x28': ('Cheat8',       self.skip(5)),
                               '\x29': ('Cheat9',       self.skip(0)),
                               '\x2A': ('Cheat10',      self.skip(0)),
                               '\x2B': ('Cheat11',      self.skip(0)),
                               '\x2C': ('Cheat12',      self.skip(0)),
                               '\x2D': ('Cheat13',      self.skip(5)),
                               '\x2E': ('Cheat14',      self.skip(4)),
                               '\x2F': ('Cheat15',      self.skip(0)), 
                               '\x30': ('Cheat16',      self.skip(0)),
                               '\x31': ('Cheat17',      self.skip(0)),
                               '\x32': ('Cheat18',      self.skip(0)),
                               '\x50': ('ChangeAllyOptions', self.handleChangeAllyOptions),
                               '\x51': ('TransferResources', self.handleTransferResources),
                               '\x60': ('MapTriggerChatCommand', self.handleMapTriggerChatCommand),
                               '\x61': ('EscPressed', self.handleEscPressed),
                               '\x62': ('unknown',       self.skip(12)),
                               '\x66': ('EnterSkillMenu', self.handleEnterSkillMenu),
                               '\x67': ('EnterBuildingsMenu', self.handleEnterBuildingsMenu),
                               '\x68': ('MinimapSignal', self.handleMinimapSignal),
                               '\x69': ('ContinueGame', self.handleContinueGame),
                               '\x6A': ('ContinueGameB', self.handleContinueGame),
                               '\x75': ('unknown', self.skip(1)), 
                               '\x6B': ('DotaInfo', self.handleDotaInfo)}   # DOTA
                              

    # GAMEDATA BLOCKS
    def handleLeaveGame(self):
        reason, player_id, result, nothing = self.read("IBII")
        return {'type': 'LEAVEGAME', 'data': {'reason': reason, 'player_id': player_id, 'result': result}}

    def handleTimeSlot(self):
        num_bytes, time_increment = self.read("<HH")
        command_blocks = []

        pos = 2
        while pos < num_bytes:
            #print " - (Start of Command Data Block)"
            command_block = self.parse_command_block()
            command_blocks.append(command_block)
            #print " - (End of Command Data Block)"
            pos += command_block['size']
        return {'type': 'TIMESLOT', 'data': {'time': 'NONE', 'command_blocks': command_blocks}}

    def handleChatMessage(self):
        player_id, num_bytes, flags, mode = self.read("<BHBI")
        message = self.read_string()
        return {'type': 'CHATMESSAGE', 'data': {'player_id': player_id, 'flags': flags, 'mode': mode, 'message': message}}

    def handleForceGameEnd(self):
        mode, countdown_time = self.read("<II")
        return {'type': 'FORCEEND', 'data': {'mode': mode, 'countdown_time': countdown_time}}

    # ACTION BLOCKS
    def handleDotaInfo(self):
        a = self.read_string()
        b = self.read_string()
        c = self.read_string()

        d = None
        if c[0] in ['8', '9'] or c.startswith("PUI_") or c.startswith("DRI_"):
            d = self.read('4s')[0][::-1].replace('\0', '') or None
        else:
            d, = self.read('L')

        return {'name': 'DotaInfo', 'data': {'strings': (b, c, d)}}

    def handlePauseGame(self):
        return {'name': 'PauseGame', 'data': {}}

    def handleResumeGame(self):
        return {'name': 'ResumeGame', 'data': {}}

    def handleSetGamespeed(self):
        d = {'speed': self.read(1)}
        return {'name': 'SetGamespeed', 'data': d}

    def handleIncrGamespeed(self):
        return {'name': 'IncreaseGamespeed', 'data': {}}

    def handleDecrGamespeed(self):
        return {'name': 'DecreaseGamespeed', 'data': {}}

    def handleSaveGame(self):
        d = {'name': self.read_string()}
        return {'name': 'SaveGame', 'data': d}

    def handleSaveGameFinished(self):
        self.read("I")
        return {'name': 'SaveGameFinished', 'data': {}}
        
    def handleUnitAbility(self):
        # TODO
        self.read(14)
        return {'name': 'UnitAbility', 'data': {}}

    def handleUnitAbilityTargetPos(self):
        # TODO
        self.read(22)
        return {'name': 'UnitAbilityTargetPosition', 'data': {}}

    def handleUnitAbilityTargetPosObj(self):
        # TODO
        self.read(30)
        return {'name': 'UnitAbilityTargetPositionAndObject', 'data': {}}

    def handleUnitAbilityTargetTwoPosObj(self):
        # TODO
        self.read(43)
        return {'name': 'UnitAbilityTargetTwoPositionsAndObjects', 'data': {}}

    def handleDropItem(self):
        # TODO
        self.read(38)
        return {'name': 'DropItem', 'data': {}}

    def handleChangeSelection(self):
        # TODO
        mode, num_units = self.read("<BH")
        for i in range(num_units):
            obj1, obj2 = self.read("II")
        return {'name': 'ChangeSelection', 'data': {}}

    def handleAssignGroupHotkey(self):
        # TODO
        group_number, num_units = self.read("<BH")
        for i in range(num_units):
            obj1, obj2 = self.read("II")
        return {'name': 'AssignGroupHotkey', 'data': {}}

    def handleSelectGroupHotkey(self):
        d = dict()
        d['group_number'] = self.read("<BB")[0]
        return {'name': 'SelectGroupHotkey', 'data': d}

    def handleSelectSubgroup(self):
        # TODO
        item_id, obj1, obj2 = self.read("<III")
        return {'name': 'SelectSubgroup', 'data': {}}

    def handleUpdateSubgroup(self):
        return {'name': 'UpdateSubgroup', 'data': {}}

    def handleSelectGroundItem(self):
        # TODO
        flags, obj1, obj2 = self.read("<BII")
        return {'name': 'SelectGroundItem', 'data': {}}

    def handleCancelHeroRevival(self):
        # TODO
        unit1, unit2 = self.read("<II")
        return {'name': 'CancelHeroRevival', 'data': {}}

    def handleRemoveUnitFromBuildingQueue(self):
        # TODO
        slot_number, unit = self.read("<BI")
        return {'name': 'RemoveUnitFromBuildingQueue', 'data': {}}

    def handleChangeAllyOptions(self):
        # TODO
        slot_number, flags = self.read("<BI")
        return {'name': 'ChangeAllyOptions', 'data': {}}

    def handleTransferResources(self):
        # TODO
        slot_number, gold, lumber = self.read("<BII")
        return {'name': 'TransferResources', 'data': {}}

    def handleMapTriggerChatCommand(self):
        self.read("II")
        self.read_string()
        return {'name': 'MapTriggerChatCommand', 'data': {}}

    def handleEscPressed(self):
        return {'name': 'EscPressed', 'data': {}}

    def handleScenarioTrigger(self):
        self.read("III")
        return {'name': 'ScenarioTrigger', 'data': {}}

    def handleEnterSkillMenu(self):
        return {'name': 'EnterSkillMenu', 'data': {}}

    def handleEnterBuildingsMenu(self):
        return {'name': 'EnterBuildingsMenu', 'data': {}}

    def handleMinimapSignal(self):
        d = dict()
        d['x'], d['y'] = self.read("II")
        self.read("I")
        return {'name': 'MinimapSignal', 'data': d}

    def handleContinueGame(self):
        self.read('IIII')
        return {'name': 'ContinueGame', 'data': {}}

    def parse_action_block(self):
        a_id = self.read(1)
        #print " - ACTION BLOCK: ", repr(a_id), self.action_blocks[a_id][0]

        if not self.action_blocks.has_key(a_id):
            print "Unexpected Action Block (%s)" % repr(a_id)
            print "Next 10 Bytes: %s" % repr(self.read(10))
            self.data.seek(self.data.tell() - 26)
            print "Previous 10 Bytes: %s" % repr(self.read(15))
            sys.exit()

        return self.action_blocks[a_id][1]()

    def parse_command_block(self):
        player_id, actions_length = self.read("<BH")
        actions = []

        pos = self.data.tell()
        end = self.data.tell() + actions_length
        while pos < end:
            actions.append(self.parse_action_block())
            pos += self.data.tell() - pos
        
        return {'actions': actions, 'size': actions_length+3}
    def skip(self, n):
        return lambda: self.read(n)

    def read(self, length):
        if isinstance(length, str):
            fmt = struct.Struct(length)
            return fmt.unpack(self.data.read(fmt.size))
        return self.data.read(length)

    def read_string(self):
        s = ''
        c = self.read(1)
        while c != '\0':
            s += c
            c = self.read(1)
        return s

    def parse(self):
        gamedata = []
        while True:
            block_id = self.read(1)
    
            if not self.blocks.has_key(block_id):
                return gamedata
                print "Unexpected Block (%s), exitting..." % repr(block_id)
                sys.exit()
            
            #print "GAMEDATA BLOCK: ", repr(block_id)
            gamedata.append(self.blocks[block_id][1]())

W3Game("/home/mephory/g.w3g").parse()
