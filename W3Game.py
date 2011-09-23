import struct
import zlib
from collections import namedtuple

W3G_HEADER_FORMAT = "28sIIIII4sIHHII"

headertpl = namedtuple('Header', 'IDString first_data_block compressed_size header_version decompressed_size num_data_blocks version_string version_number build_number flags replay_len crc32')
staticdatatpl = namedtuple('StaticData', 'players slots gamename')

class Player:
    def __init__(self, record_id, id, name, gametype):
        self.record_id = record_id
        self.id = id
        self.name = name
        self.gametype = gametype

    def __repr__(self):
        return "<Player \"%s\">" % self.name

class Slot:
    def __init__(self, player_id, download_percent, status, comp_flag, team_nr, color, race_flag, comp_ai_level, handicap):
        self.player_id = player_id
        self.download_percent = download_percent
        self.status = status
        self.comp_flag = comp_flag
        self.team_nr = team_nr
        self.color = color
        self.race_flag = race_flag
        self.comp_ai_level = comp_ai_level
        self.handicap = handicap

    def __repr__(self):
        return "<Slot \"%s\">" % self.color

class Action:
    def __init__(self):
        pass

class DataBlock:    
    def __init__(self, size, decompressed_size, unknown_checksum, compressed_data):
        self.pos = 0
        self.size = size
        self.decompressed_size = decompressed_size
        self.unknown_checksum = unknown_checksum
        self.compressed_data = compressed_data
        self.raw_data = ""

    def decompress(self):
        self.raw_data = zlib.decompress(self.compressed_data)

    def read_bytes(self, n):
        self.pos += n
        return self.raw_data[self.pos-n:self.pos]

    def read_string(self):
        s = ''
        while self.raw_data[self.pos] != '\0':
            s += self.raw_data[self.pos]
            self.pos += 1
        self.pos += 1
        return s

    def read_player_record(self):
        record_id = self.read_bytes(1)
        player_id = ord(self.read_bytes(1))
        player_name = self.read_string()
        gametype = self.read_bytes(1)
        if gametype == '\x01':
            self.pos += 1
        else:
            self.pos += 8
        return Player(record_id, player_id, player_name, gametype)

    def read_slot_record(self):
        player_id = ord(self.read_bytes(1))
        download_percent = ord(self.read_bytes(1))
        slot_status = self.read_bytes(1)
        comp_flag = self.read_bytes(1)
        team_nr = ord(self.read_bytes(1))
        color = ord(self.read_bytes(1))
        plr_race_flag = self.read_bytes(1)
        comp_ai_strength = self.read_bytes(1)
        plr_handicap = ord(self.read_bytes(1))
        return Slot(player_id, download_percent, slot_status, comp_flag, team_nr, color, plr_race_flag, comp_ai_strength, plr_handicap)

    def read(self):
        self.pos = 4

        players = []
        slots = []

        # Player Record
        players.append(self.read_player_record())

        # Game Name
        gamename = self.read_string()

        # Encoded String
        self.pos += 1
        enc_str = self.read_string()

        # Player Count
        self.pos += 0
        player_count = struct.unpack("I", self.read_bytes(4))[0]

        # Game Type
        gt_gametype = self.read_bytes(1)
        gt_privateflag = self.read_bytes(1)
        self.read_bytes(2)

        # Language
        language = self.read_bytes(4)

        # PlayerList
        while True:
            if self.raw_data[self.pos] != '\x16':
                break
            players.append(self.read_player_record())
            self.read_bytes(4)
        
        # GameStart Record
        record_id = self.read_bytes(1)
        size = self.read_bytes(2)
        num_slotrecords = ord(self.read_bytes(1))
        for i in range(0, num_slotrecords):
            slot = self.read_slot_record()
            slots.append(slot)
        random_seed = self.read_bytes(4)
        select_mode = self.read_bytes(1)
        num_startspots = self.read_bytes(1)

        return staticdatatpl._make((players, slots, gamename))

    def read_actions(self, start=0):
        # Actions
        while self.pos < len(self.raw_data) - 5:
            aid = self.read_bytes(1)

            # unknown (5 bytes)
            if aid == '\x1a':
                self.read_bytes(4)

            # unknown (5 bytes)
            elif aid == '\x1b':
                self.read_bytes(4)

            # unknown (5 bytes)
            elif aid == '\x1c':
                self.read_bytes(4)

            # timeslot block OLD (n+3 bytes)
            elif aid == '\x1e':
                siz = struct.unpack("H", self.read_bytes(2))[0]
                self.read_bytes(siz)

            # timeslot block (n+3 bytes)
            elif aid == '\x1f':
                siz = struct.unpack("H", self.read_bytes(2))[0]
                self.read_bytes(siz)

            # player chat message (n+4 bytes)
            elif aid == '\x20':
                player_id = ord(self.read_bytes(1))
                siz = self.read_bytes(2)
                flags = self.read_bytes(1)
                chat_mode = self.read_bytes(4)
                msg = self.read_string()

            # unknown (checksum?) (6 bytes)
            elif aid == '\x22':
                self.read_bytes(5)

            # unknown (11 bytes)
            elif aid == '\x23':
                self.read_bytes(10)

            # forced game end countdown (9 bytes)
            elif aid == '\x2f':
                mode = self.read_bytes(4)
                countdown_time = self.read_bytes(4)
            
            # leave game (14 bytes)
            elif aid == '\x17':
                reason = self.read_bytes(4)
                player_id = ord(self.read_bytes(1))
                result = self.read_bytes(4)
                self.read_bytes(4)

class W3Game:
    def __init__(self, replayfile):
        self.replayfile = open(replayfile)
        self.raw_data = self.replayfile.read()

        self.players = []
        self.slots = []
        self.actions = []

        self.gamename = ""
        
        self.parse()

    def parse(self):
        self.pos = 0

        # Read Header
        self.header = headertpl._make(struct.unpack(W3G_HEADER_FORMAT, self.raw_data[:68]))
        self.pos += 68

        # Read DataBlocks
        self.datablocks = []
        datablock_num = 0
        while datablock_num < self.header.num_data_blocks:
            siz_compr, siz_decompr, checksum = struct.unpack("HHI", self.raw_data[self.pos:self.pos+8])
            data_compr = self.raw_data[self.pos+8:self.pos+8+siz_compr]
            
            db = DataBlock(siz_compr, siz_decompr, checksum, data_compr)
            db.decompress()
            self.datablocks.append(db)

            self.pos += 8 + siz_compr
            datablock_num += 1

        static_data = self.datablocks[0].read()

        for block in self.datablocks:
            action_data = block.read_actions()

        self.players = static_data.players
        self.slots = static_data.slots
        self.gamename = static_data.gamename

g = W3Game("/home/mephory/t.w3g")
