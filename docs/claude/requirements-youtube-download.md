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

# Spotify downloads (added 2026-10-12)
The same page accepts Spotify links. They are handled by spotDL (`pip install spotdl`,
MIT, no Spotify login needed). spotDL fetches the metadata from Spotify and the audio
from YouTube Music, so Deno and ffmpeg from the yt-dlp setup are reused.

* Track links are saved directly in the selected folder as `Artist - Title.mp3`.
* Playlist and album links are saved in a new folder named after the list inside
  the selected folder, with a position prefix (`03 Title.mp3`) so the audio player
  keeps the list order.
* Artist links (whole discography) are rejected.
* spotDL only embeds the cover into the mp3 tags; `stream_toy/cover_art.py`
  extracts it to `<name>.jpg` next to the file for the audio player.
* `spotify.link` short links are resolved by following the redirect first.
* spotDL is started through `stream_toy/spotdl_runner.py` instead of the `spotdl`
  script. spotDL 4.5.2 creates its YouTube Music client with `language="de"`, which
  returns zero song results with ytmusicapi 1.12.x (spotDL issue #2779), so nothing
  but popular tracks would be found. The runner swaps in a default-language client.
  Remove it once upstream is fixed.
* Limitation: spotDL downloads what YouTube Music has, not the Spotify stream.
  Spotify exclusive content, or releases that are cut differently on YouTube Music
  (e.g. audiobook chapters), come out incomplete or mismatched. The completion
  message reports "x of y tracks" in that case; details are in the log.

Working command:
python stream_toy/spotdl_runner.py download <url> --format mp3 --simple-tui --print-errors --threads 1 --output "{list-name}/{list-position} {title}.{output-ext}"
