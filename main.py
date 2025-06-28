import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import json
import time

# --- Constants ---
# Adjust based on your usage. A smaller number is safer for quotas.
# Rough estimate: 25 songs * (100 units/search + 50 units/add) = 3750 units per batch.
BATCH_SIZE = 25 

# --- Spotify Configuration ---
# IMPORTANT: Fill these in with your actual credentials from the Spotify Developer Dashboard.
SPOTIPY_CLIENT_ID = 'YOUR_SPOTIFY_CLIENT_ID'
SPOTIPY_CLIENT_SECRET = 'YOUR_SPOTIFY_CLIENT_SECRET'
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback' # Must match your Spotify Dashboard

# --- YouTube Configuration ---
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'
YOUTUBE_SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
CLIENT_SECRETS_FILE = 'client_secret.json' # Must be in the same directory

# --- Custom Exception for Quota ---
class QuotaExceededException(Exception):
    """Custom exception for YouTube API quota errors."""
    pass

# --- 1. Authenticate with Spotify ---
def authenticate_spotify():
    print("Attempting Spotify authentication (Authorization Code Flow)...")
    auth_manager = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative",
        open_browser=False,
        cache_path=".spotifycache"
    )

    print("\n>>> SPOTIFY AUTHENTICATION INSTRUCTIONS <<<")
    print("Spotipy will now print an authorization URL.")
    print("1. COPY the long URL that Spotipy prints.")
    print("2. PASTE it into your web browser and press Enter.")
    print("3. Log in to Spotify (if prompted) and AUTHORIZE the application.")
    print("4. After authorizing, your browser will be REDIRECTED. The address bar will now show a URL")
    print(f"   starting with '{SPOTIPY_REDIRECT_URI}?code=...'")
    print("   You will likely see a browser error page like 'This site can’t be reached' - THIS IS NORMAL.")
    print("5. COPY THE ENTIRE URL from your browser's address bar (the one with '?code=...').")
    print("6. PASTE this copied URL back into THIS terminal when Spotipy prompts 'Enter the URL you were redirected to:'.")
    print("---------------------------------------------------\n")

    sp = spotipy.Spotify(auth_manager=auth_manager)
    user = sp.current_user()
    print(f"\nSuccessfully authenticated with Spotify as {user['display_name']}.")
    return sp

# --- 2. Get Spotify Playlist Tracks ---
def get_spotify_playlist_tracks(sp, playlist_url_or_id):
    if not playlist_url_or_id:
        print("ERROR: Playlist URL or ID input is empty.")
        return []

    if "open.spotify.com/playlist/" in playlist_url_or_id:
        playlist_id = playlist_url_or_id.split('/')[-1].split('?')[0]
    else:
        playlist_id = playlist_url_or_id

    print(f"Fetching tracks for Spotify playlist ID: '{playlist_id}'...")
    tracks = []
    results = sp.playlist_items(playlist_id)
    
    while results:
        for item in results.get('items', []):
            track = item.get('track')
            if track and track.get('name'):
                artist_name = track.get('artists', [{}])[0].get('name', 'Unknown Artist')
                tracks.append({'name': track['name'], 'artist': artist_name})
        if results.get('next'):
            results = sp.next(results)
        else:
            results = None
            
    print(f"Fetched {len(tracks)} total tracks from Spotify playlist.")
    return tracks

# --- 3. Authenticate with YouTube ---
def authenticate_youtube():
    print("\nAttempting YouTube authentication...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, YOUTUBE_SCOPES)
    credentials = flow.run_local_server(port=0)
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)
    print("Successfully authenticated with YouTube.")
    return youtube

# --- 4. Search for Song on YouTube ---
def search_youtube_video(youtube, song_name, artist_name):
    query = f"{song_name} {artist_name} official audio"
    try:
        search_response = youtube.search().list(q=query, part='snippet', maxResults=1, type='video').execute()
        if search_response.get('items'):
            return search_response['items'][0]['id']['videoId']
        else:
            print(f"    - Could not find video for: {song_name} - {artist_name}")
            return None
    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in e.content.decode():
            raise QuotaExceededException("YouTube API quota exceeded during search.")
        else:
            print(f"    - An HTTP error occurred during YouTube search for '{query}': {e}")
            return None

# --- 5. Create YouTube Playlist ---
def create_youtube_playlist(youtube, title, description=""):
    try:
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": description, "tags": ["spotify_conversion", "music"]},
                "status": {"privacyStatus": "private"}
            }
        ).execute()
        playlist_id = request['id']
        print(f"\nCreated YouTube playlist: '{title}' (ID: {playlist_id})")
        return playlist_id
    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in e.content.decode():
            raise QuotaExceededException("YouTube API quota exceeded during playlist creation.")
        else:
            print(f"An HTTP error occurred creating YouTube playlist: {e}")
            return None

# --- 6. Add Video to YouTube Playlist ---
def add_video_to_youtube_playlist(youtube, playlist_id, video_id, song_name_for_log=""):
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id}
                }
            }
        ).execute()
        return True
    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in e.content.decode():
            raise QuotaExceededException(f"YouTube API quota exceeded while adding '{song_name_for_log}'.")
        else:
            print(f"    - An HTTP error occurred adding video {video_id} to playlist {playlist_id}: {e}")
            return False

# --- Main Execution ---
if __name__ == '__main__':
    # --- Check for API Keys ---
    if 'YOUR_SPOTIFY_CLIENT_ID' in SPOTIPY_CLIENT_ID or 'YOUR_SPOTIFY_CLIENT_SECRET' in SPOTIPY_CLIENT_SECRET:
        print("!!! ERROR: Please fill in your Spotify API credentials at the top of the script.")
        exit()

    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"!!! ERROR: YouTube client secrets file ('{CLIENT_SECRETS_FILE}') not found.")
        exit()

    print("Spotify to YouTube Playlist Converter")
    print("------------------------------------")

    try:
        sp = authenticate_spotify()
        youtube = authenticate_youtube()
    except Exception as e:
        print(f"\nAuthentication failed: {e}")
        exit()

    spotify_playlist_link = input("\nEnter your Spotify Playlist URL or ID: ")
    all_spotify_tracks = get_spotify_playlist_tracks(sp, spotify_playlist_link)

    if not all_spotify_tracks:
        print("\nNo tracks found in the Spotify playlist. Exiting.")
        exit()

    youtube_playlist_name_input = input("\nEnter a name for your new YouTube Playlist: ")
    
    youtube_playlist_id = create_youtube_playlist(youtube, youtube_playlist_name_input, f"Converted from Spotify playlist: {spotify_playlist_link}")
    
    if not youtube_playlist_id:
        print("\nCould not create YouTube playlist. Exiting.")
        exit()

    total_tracks_to_process = len(all_spotify_tracks)
    processed_count = 0
    overall_added_count = 0
    overall_not_found_count = 0

    while processed_count < total_tracks_to_process:
        start_index = processed_count
        end_index = min(processed_count + BATCH_SIZE, total_tracks_to_process)
        current_batch = all_spotify_tracks[start_index:end_index]

        print(f"\n--- Processing Batch: Songs {start_index + 1} to {end_index} (out of {total_tracks_to_process}) ---")
        quota_hit_in_batch = False

        for i, track in enumerate(current_batch):
            current_song_number_overall = start_index + i + 1
            print(f"  ({current_song_number_overall}/{total_tracks_to_process}) Processing: {track['name']} - {track['artist']}")
            try:
                video_id = search_youtube_video(youtube, track['name'], track['artist'])
                if video_id:
                    if add_video_to_youtube_playlist(youtube, youtube_playlist_id, video_id, track['name']):
                        print(f"    + Added '{track['name']}' to YouTube playlist.")
                        overall_added_count += 1
                else:
                    overall_not_found_count += 1
                
                time.sleep(0.2) # Small delay to be kinder to the API

            except QuotaExceededException as e:
                print(f"\n    ! {e}")
                quota_hit_in_batch = True
                break # Stop processing this batch
            except Exception as e:
                print(f"    - An unexpected error occurred processing '{track['name']}': {e}")
                overall_not_found_count += 1
                continue

        processed_count = start_index + len(current_batch)

        if quota_hit_in_batch:
            print("\n-----------------------------------------------------------")
            print("YOUTUBE API QUOTA EXCEEDED. Processing stopped for now.")
            print("Please wait for your quota to reset (usually midnight Pacific Time).")
            print("This script does not support auto-resuming, you will have to restart the process.")
            break

        if processed_count < total_tracks_to_process:
            print(f"--- End of Batch ---")
            user_choice = input("Continue with the next batch? (yes/no): ").lower()
            if user_choice not in ['yes', 'y']:
                print("Stopping as per user request.")
                break
        else:
            print("\nAll tracks from Spotify playlist have been processed.")

    print("\n--- Conversion Summary ---")
    print(f"Total songs from Spotify playlist: {total_tracks_to_process}")
    print(f"Successfully added {overall_added_count} songs to the YouTube playlist.")
    if overall_not_found_count > 0:
        print(f"{overall_not_found_count} songs were not found or could not be added.")
    print(f"Your YouTube playlist: https://www.youtube.com/playlist?list={youtube_playlist_id}")
