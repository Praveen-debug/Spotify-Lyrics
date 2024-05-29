import time
import spotipy
import datetime
import syncedlyrics
import threading
import os


class Main:
    """
    This class handles the main functionality of the program, including:
    - Getting the currently playing song from Spotify
    - Downloading lyrics for the current song
    - Playing the lyrics in sync with the song
    """

    scope = "user-read-currently-playing"
    """
    The scope of the Spotify API access token. This scope allows the program to read the currently playing song.
    """

    song = None
    """
    The currently playing song. This is a string containing the song title and artist name.
    """

    counter = 0
    """
    A counter used to track the current line of lyrics.
    """

    oldTime = 0
    """
    The time of the last played line of lyrics.
    """

    startAgain = False
    """
    A flag indicating whether to start playing lyrics from the beginning.
    """

    count = 0
    """
    A counter used to track the number of times a song has been skipped.
    """

    current_time = datetime.datetime.now()
    """
    The current time.
    """

    startTime = float(current_time.minute) * 60 + float(str(current_time.second) + "." + str(current_time.microsecond))
    """
    The time the program started.
    """

    spotifyOAuth = spotipy.SpotifyOAuth(*CREADS)
    """
    A SpotifyOAuth object used to authenticate with the Spotify API.
    """

    paused = False
    """
    A flag indicating whether the song is paused.
    """

    skiped = False
    """
    A flag indicating whether the song has been skipped.
    """

    updated_time = 0
    """
    The last time the progress of the song was updated.
    """

    stop_thread = False
    """
    A flag indicating whether to stop the lyrics thread.
    """

    def get_current(self):
        """
        Gets the currently playing song from the Spotify API.

        Returns:
            A dictionary containing information about the currently playing song.
        """

        token = self.spotifyOAuth.get_cached_token()
        spotifyObject = spotipy.Spotify(auth=token['access_token'])
        current = spotifyObject.currently_playing()
        return current
    
    def ms_to_sec(self, ms):
        """
        Converts milliseconds to seconds.

        Args:
            ms: The number of milliseconds to convert.

        Returns:
            The number of seconds.
        """

        total_seconds = ms / 1000
        minutes = int(total_seconds // 60)
        min_secs = int(minutes * 60)
        seconds = int(total_seconds % 60) + min_secs
        time_str = f"{seconds}"
        return time_str

    def ts_to_sec(self, ts):
        """
        Converts a timestamp in the format "[mm:ss]" to seconds.

        Args:
            ts: The timestamp to convert.

        Returns:
            The number of seconds.
        """

        ts = str(ts)
        ts = ts.replace("]", "").replace("[", "")
        ts = ts.split(".")[0]
        seconds = int(ts.split(":")[0]) * 60 + int(ts.split(":")[1])
        return seconds

    def get_song(self):
        """
        Gets the currently playing song and sets the `song` attribute.
        """

        while True:
            current = self.get_current()
            current_type = current['currently_playing_type']
            if current_type == "track":
                title = "[" + current['item']['name'] + "] [" + current["item"]["artists"][0]["name"] + "]"
                print("Got track", title)
                length_ms = current['item']['duration_ms']
                progress_ms = current['progress_ms']
                self.updated_time = int(self.ms_to_sec(int(current["progress_ms"])))
                self.song = title
                break
            elif current_type == "ad":
                print(">> ad popped up -- sleeping...")
                time.sleep(30)
                continue
            if self.spotifyOAuth.is_token_expired(token):
                print(">> access token has expired -- refreshing...")
                token = self.spotifyOAuth.get_access_token()
                spotifyObject = spotipy.Spotify(auth=token['access_token'])

    def getlyrics(self):
        """
        Downloads the lyrics for the current song and saves them to a file.
        """

        print("Getting lyrics")
        if not os.path.exists(f"./Lyrics/{self.song}" + ".lrc"):
            lrc = syncedlyrics.search(self.song)
            with open(f"Lyrics/{self.song}" + ".lrc", "w", encoding="utf-8") as f:
                f.write(lrc)
                f.close()
        print("Got lyrics")

    def play_line(self, pause_event):
        """
        Plays the lyrics for the current line of the song.

        Args:
            pause_event: A threading event used to pause and resume the lyrics playback.
        """

        current = self.get_current()
        progress_ms = int(self.ms_to_sec(int(current["progress_ms"])))
        lines = None
        counter = 0
        last_time = 0
        with open(f"Lyrics/{self.song}" + ".lrc", "r", encoding="utf-8") as f:
            lines = f.read()
            lines = lines.split("\n")
        i = 0
        while i <= len(lines) - 1:
            if pause_event.is_set():
                print("Song paused!")
                while pause_event.is_set():
                    time.sleep(0.1)
                print("Song resumed")
            ts = lines[i].split("]")[0]
            ts = self.ts_to_sec(ts)
            if counter == 0:
                if ts >= progress_ms:
                    self.sleep_check_pause(int(ts) - int(progress_ms), pause_event)
                    print(lines[i].split("]")[1], "\n\n")
                    if self.paused:
                        i = 0
                        counter = 0
                        self.paused = False
                        continue
                    last_time = ts
                    counter += 1
                else:
                    i += 1
                    continue
            else:
                ts = lines[i].split("]")[0]
                ts = self.ts_to_sec(ts)
                self.sleep_check_pause(ts - last_time, pause_event)
                if self.paused:
                    i = 0
                    counter = 0
                    self.paused = False
                    progress_ms = int(self.ms_to_sec(self.get_current()["progress_ms"]))
                    continue
                print(lines[i].split("]")[1], "\n\n")
                last_time = ts
            i += 1

    def show_lyrics(self):
        """
        Starts a thread to play the lyrics for the current song.
        """

        pause_event = threading.Event()
        thread = threading.Thread(target=self.play_line, args=(pause_event,))
        thread.start()
        paused = False
        resumed = True
        while True:
            current = self.get_current()
            try:
                resuming = current["actions"]["disallows"]["resuming"]
                if not resumed:
                    pause_event.clear()
                    resumed = True
                    paused = False
            except Exception as e:
                if not paused:
                    pause_event.set()
                    resumed = False
                    paused = True
            time.sleep(1)

    def sleep_check_pause(self, duration, pause_event):
        """
        Sleeps for a specified duration, checking for pauses in the song.

        Args:
            duration: The duration to sleep for.
            pause_event: A threading event used to pause and resume the lyrics playback.
        """

        start_time = time.time()
        while time.time() - start_time < duration:
            if pause_event.is_set():
                print("Song paused!")
                while pause_event.is_set():
                    time.sleep(0.1)
                self.paused = True
                if not pause_event.is_set():
                    print("Song resumed!")
                return
            time.sleep(0.1)
        


if __name__ == '__main__':
    print("Program Made by Praveen K, Github:- Praveen-debug")
    lyrics = Main()
    lyrics.get_song()
    lyrics.getlyrics()
    lyrics.show_lyrics()
