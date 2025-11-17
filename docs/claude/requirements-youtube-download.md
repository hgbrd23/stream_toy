# Requirements
Add a route in the WebDevice to open a page for downloading Youtube Music.

One input field for pasting the URL. If possible load the title and display it as soon as the URL is pasted.

Below show a directory listing of the directory "data/audio_player". Only display audio files in the listing.
Allow selecting directories, then enter the directory and update the list.

Allow going a directory up and also show a breadcrumb of the path and allow navigating by clicking on the path segments.

Underneath add a button "Start Download". Then call yt-dlp. Display a log of the output of yt-dlp that is updated in 
realtime.

Add a metadata service that is used by this download to store download url and download time. The metadata should be 
saved next to the audio file with the same filename and extension .yml as YAML file. 

The metadata service should also be used by audio_player and save last play time and current play position. The 
position should be updated every 30s. Current playing position should be removed when playing is finished.  
When starting playing again, playing should resume at the last saved position.

Working command:
yt-dlp --extract-audio --audio-format mp3 --write-thumbnail https://www.youtube.com/watch?v=xxxxx
