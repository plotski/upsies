import os

if os.name == 'nt':
    ffmpeg = 'ffmpeg.exe'
    ffprobe = 'ffprobe.exe'
    mediainfo = 'mediainfo.exe'
else:
    ffmpeg = 'ffmpeg'
    ffprobe = 'ffprobe'
    mediainfo = 'mediainfo'
