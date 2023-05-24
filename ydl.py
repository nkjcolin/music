import yt_dlp

a=input("Enter URL:")

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors':[{
    'key':'FFmpegExtractAudio',
    'preferredcodec': 'mp3',
    'preferredquality': '192',}],
    
    }
    
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([a])
