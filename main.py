import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import json

# --- Spotify Configuration ---
SPOTIPY_CLIENT_ID = 'YOUR_SPOTIFY_CLIENT' 
SPOTIPY_CLIENT_SECRET = 'YOUR_CLIENT_SECRET'
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback' # Or your configured one

# --- YouTube Configuration ---
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'
YOUTUBE_SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
CLIENT_SECRETS_FILE = 'client_secret.json' # Downloaded from Google Cloud Console

# --- 1. Authenticate with Spotify ---
def authenticate_spotify():
    print("Attempting Spotify authentication (using PKCE flow)...") # Indicate PKCE
    print(f"USING: Client ID: {SPOTIPY_CLIENT_ID}")
    print(f"USING: Redirect URI: {SPOTIPY_REDIRECT_URI}")
    print(f"Ensure your Redirect URI in Spotify Developer Dashboard is EXACTLY: {SPOTIPY_REDIRECT_URI}")

    auth_manager = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative",
        open_browser=False, # Keep this false to manually copy the auth URL
        cache_path=".spotifycache"
    )

    print("\n>>> SPOTIFY AUTHENTICATION INSTRUCTIONS (PKCE Flow) <<<")
    print("Spotipy will now print an authorization URL.")
    print("1. COPY the long URL that Spotipy prints.")
    print("2. PASTE it into your web browser's address bar and press Enter.")
    print("3. Log in to Spotify (if prompted) and AUTHORIZE the application.")
    print("4. After authorizing, your browser will be REDIRECTED. The address bar will now show a URL")
    print(f"   starting with '{SPOTIPY_REDIRECT_URI}?code=...' (e.g., https://localhost:8888/callback?code=...).")
    print("   You will likely see a browser error page like 'This site can’t be reached' - THIS IS NORMAL.")
    print("5. COPY THE ENTIRE URL from your browser's address bar (the one with '?code=...').")
    print("6. PASTE this copied URL back into THIS terminal when Spotipy prompts 'Enter the URL you were redirected to:'.")
    print("---------------------------------------------------\n")

    sp = spotipy.Spotify(auth_manager=auth_manager)
    try:
        user = sp.current_user()
        if user and user.get('display_name'):
            print(f"\nSuccessfully authenticated with Spotify as {user['display_name']}.")
        else:
            print("\nSuccessfully obtained Spotify token (or using cached token).")
    except spotipy.oauth2.SpotifyOauthError as e:
        print(f"\nSPOTIFY AUTHENTICATION FAILED (PKCE attempt): {e}")
        # ... (troubleshooting) ...
        raise
    except Exception as e:
        print(f"An unexpected error occurred during Spotify authentication (PKCE attempt): {e}")
        raise
    return sp

# --- 2. Get Spotify Playlist Tracks ---
def get_spotify_playlist_tracks(sp, playlist_url_or_id):
    """Fetches tracks (name and artist) from a Spotify playlist."""
    print(f"DEBUG: Received playlist_url_or_id: '{playlist_url_or_id}'") # For debugging input

    if not playlist_url_or_id: # Add a check for empty input
        print("ERROR: Playlist URL or ID input is empty.")
        return [] # Return an empty list or raise an error

    if "open.spotify.com/playlist/" in playlist_url_or_id:
        playlist_id = playlist_url_or_id.split('/')[-1].split('?')[0]
    else:
        playlist_id = playlist_url_or_id

    print(f"DEBUG: Extracted playlist_id: '{playlist_id}'") # CRITICAL DEBUG LINE

    tracks = []
    try:
        results = sp.playlist_items(playlist_id)
        # ... rest of your track processing
    except spotipy.exceptions.SpotifyException as e:
        print(f"ERROR fetching playlist items for ID '{playlist_id}': {e}")
        print("Please ensure you entered a valid Spotify Playlist URL or just the Playlist ID.")
        return [] # Return empty list on error
    # ... (your existing track processing code)
    for item in results['items']:
        track = item['track']
        if track: # Sometimes track can be None (e.g., local files)
            track_name = track['name']
            artist_name = track['artists'][0]['name'] # Taking the primary artist
            tracks.append({'name': track_name, 'artist': artist_name})

    # Handle pagination if playlist is longer than 100 tracks
    while results.get('next'): # Use .get() for safety
        results = sp.next(results)
        for item in results['items']:
            track = item['track']
            if track:
                track_name = track['name']
                artist_name = track['artists'][0]['name']
                tracks.append({'name': track_name, 'artist': artist_name})
    
    print(f"Fetched {len(tracks)} tracks from Spotify playlist.")
    return tracks

# --- 3. Authenticate with YouTube ---
def authenticate_youtube():
    """Authenticates with YouTube API and returns a YouTube service instance."""
    # Get credentials and create an API client
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, YOUTUBE_SCOPES)
    # The `InstalledAppFlow` will automatically open a browser for authentication
    # It will store credentials in 'token.json' by default or try to load them
    credentials = flow.run_local_server(port=0) # port=0 finds a free port
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)
    print("Successfully authenticated with YouTube.")
    return youtube

# --- 4. Search for Song on YouTube ---
def search_youtube_video(youtube, song_name, artist_name):
    """Searches for a video on YouTube and returns its videoId."""
    query = f"{song_name} {artist_name} official audio" # Or 'official video', 'lyrics' etc.
    try:
        search_response = youtube.search().list(
            q=query,
            part='snippet',
            maxResults=1, # Get the top result
            type='video'
        ).execute()

        if search_response.get('items'):
            return search_response['items'][0]['id']['videoId']
        else:
            print(f"Could not find video for: {song_name} - {artist_name}")
            return None
    except Exception as e:
        print(f"An error occurred during YouTube search for '{query}': {e}")
        return None


# --- 5. Create YouTube Playlist ---
def create_youtube_playlist(youtube, title, description=""):
    """Creates a new private YouTube playlist and returns its ID."""
    try:
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["spotify_conversion", "music"],
                    "defaultLanguage": "en"
                },
                "status": {
                    "privacyStatus": "private" # or "public" or "unlisted"
                }
            }
        )
        response = request.execute()
        playlist_id = response['id']
        print(f"Created YouTube playlist: '{title}' (ID: {playlist_id})")
        return playlist_id
    except Exception as e:
        print(f"An error occurred creating YouTube playlist: {e}")
        return None

# --- 6. Add Video to YouTube Playlist ---
def add_video_to_youtube_playlist(youtube, playlist_id, video_id):
    """Adds a video to a YouTube playlist."""
    try:
        request = youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        request.execute()
        return True
    except Exception as e:
        print(f"An error occurred adding video {video_id} to playlist {playlist_id}: {e}")
        return False

# --- Main Execution ---
if __name__ == '__main__':
    # --- Check for API Keys ---
    if 'YOUR_SPOTIFY_CLIENT_ID' in SPOTIPY_CLIENT_ID or \
       'YOUR_SPOTIFY_CLIENT_SECRET' in SPOTIPY_CLIENT_SECRET:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERROR: Please set your Spotify API credentials in the script.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        exit()

    if not os.path.exists(CLIENT_SECRETS_FILE):
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"!!! ERROR: YouTube client secrets file ('{CLIENT_SECRETS_FILE}') not found.")
        print("!!! Please download it from Google Cloud Console and place it in the script's directory.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        exit()

    print("Spotify to YouTube Playlist Converter")
    print("------------------------------------")

    # 1. Spotify Authentication
    sp = authenticate_spotify()

    # 2. Get Spotify Playlist Tracks
    spotify_playlist_link = input("Enter your Spotify Playlist URL or ID: ")
    spotify_tracks = get_spotify_playlist_tracks(sp, spotify_playlist_link)

    if not spotify_tracks:
        print("No tracks found in the Spotify playlist. Exiting.")
        exit()

    # 3. YouTube Authentication
    youtube = authenticate_youtube()

    # 4. Create YouTube Playlist
    youtube_playlist_title = input("Enter the title for your new YouTube playlist: ")
    youtube_playlist_id = create_youtube_playlist(youtube, youtube_playlist_title)

    if not youtube_playlist_id:
        print("Failed to create YouTube playlist. Exiting.")
        exit()

    # 5. Search and Add Tracks to YouTube Playlist
    print(f"\nStarting to add {len(spotify_tracks)} tracks to YouTube playlist '{youtube_playlist_title}'...")
    added_count = 0
    for i, track in enumerate(spotify_tracks):
        song_name = track['name']
        artist_name = track['artist']
        print(f"[{i+1}/{len(spotify_tracks)}] Searching YouTube for: {song_name} - {artist_name}")
        video_id = search_youtube_video(youtube, song_name, artist_name)
        if video_id:
            print(f"    Found video: https://www.youtube.com/watch?v={video_id}")
            if add_video_to_youtube_playlist(youtube, youtube_playlist_id, video_id):
                print(f"    Successfully added '{song_name}' to YouTube playlist.")
                added_count += 1
            else:
                print(f"    Failed to add '{song_name}' to YouTube playlist.")
        else:
            print(f"    Skipping '{song_name}' - no suitable video found.")

    print(f"\nConversion complete! Added {added_count} out of {len(spotify_tracks)} tracks to YouTube playlist '{youtube_playlist_title}'.")
    print(f"You can view your new YouTube playlist here: https://www.youtube.com/playlist?list={youtube_playlist_id}")

    if not spotify_tracks:
        print("No tracks found or an error occurred. Exiting.")
        exit()

    # 3. YouTube Authentication
    youtube = authenticate_youtube()

    # 4. Create new YouTube Playlist
    youtube_playlist_name = input("Enter a name for your new YouTube Playlist: ")
    spotify_playlist_details = sp.playlist(spotify_playlist_link.split('/')[-1].split('?')[0] if "open.spotify.com" in spotify_playlist_link else spotify_playlist_link)
    playlist_description = f"Converted from Spotify playlist: {spotify_playlist_details['name']}. Original URL: {spotify_playlist_details['external_urls']['spotify']}"
    
    youtube_playlist_id = create_youtube_playlist(youtube, youtube_playlist_name, playlist_description)

    if not youtube_playlist_id:
        print("Failed to create YouTube playlist. Exiting.")
        exit()

    # 5. Search and Add Tracks to YouTube Playlist
    print(f"\nAdding songs to YouTube playlist '{youtube_playlist_name}'...")
    added_count = 0
    not_found_count = 0
    for i, track in enumerate(spotify_tracks):
        print(f"  ({i+1}/{len(spotify_tracks)}) Searching for: {track['name']} - {track['artist']}...")
        video_id = search_youtube_video(youtube, track['name'], track['artist'])
        if video_id:
            if add_video_to_youtube_playlist(youtube, youtube_playlist_id, video_id):
                print(f"    Added '{track['name']}' to YouTube playlist.")
                added_count += 1
            else:
                print(f"    Failed to add '{track['name']}' to YouTube playlist.")
        else:
            print(f"    Could not find a suitable YouTube video for '{track['name']} - {track['artist']}'.")
            not_found_count +=1
        
        # Simple delay to avoid hitting API limits too quickly (adjust as needed)
        # time.sleep(1) # Consider adding 'import time'

    print("\n--- Conversion Complete ---")
    print(f"Successfully added {added_count} songs to the YouTube playlist.")
    if not_found_count > 0:
        print(f"{not_found_count} songs could not be found or added to YouTube.")
    print(f"Your new YouTube playlist: https://www.youtube.com/playlist?list={youtube_playlist_id}")
