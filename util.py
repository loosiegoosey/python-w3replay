import time

def convert_time(t):
    minute = int(t/60000)
    second = int((t%60000)/1000)
    return "%02d:%02d" % (minute, second)
