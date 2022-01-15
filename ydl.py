import youtube_dl

a=input("Enter URL:")

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors':[{
    'key':'FFmpegExtractAudio',
    'preferredcodec': 'mp3',
    'preferredquality': '192',}],
    
    }
    
with youtube_dl.YoutubeDL(ydl_opts) as ydl:
    ydl.download([a])
