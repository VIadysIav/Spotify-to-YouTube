import os
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle
import google.auth.exceptions
from google.auth.transport.requests import Request

# Конфигурация Spotify API
SPOTIFY_CLIENT_ID = 'YOUR SPOTIFY CLIENT ID'
SPOTIFY_CLIENT_SECRET = 'YOUR SPOTIFY_CLIENT_SECRET'
SPOTIFY_REDIRECT_URI = 'http://localhost:8080'
SPOTIFY_SCOPE = 'playlist-read-private'

# Конфигурация YouTube API
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube"]
CREDENTIALS_FILE = 'D:/Personal information/Programming/Python/Spotify to YouTube/credentials.json'

def authenticate_spotify():
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIFY_CLIENT_ID,
                                                   client_secret=SPOTIFY_CLIENT_SECRET,
                                                   redirect_uri=SPOTIFY_REDIRECT_URI,
                                                   scope=SPOTIFY_SCOPE))
    return sp

def authenticate_youtube():
    creds = None
    # Проверка на наличие токена
    if os.path.exists("token_youtube.pkl"):
        with open("token_youtube.pkl", "rb") as token:
            creds = pickle.load(token)

    # Если токен отсутствует или его нужно обновить
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())  # Попытка обновления токена
                with open("token_youtube.pkl", "wb") as token:
                    pickle.dump(creds, token)
            except google.auth.exceptions.RefreshError:
                # Если токен нельзя обновить, проводим новую аутентификацию
                creds = None
        
        if not creds:  # Если токен не найден или не обновился, начнем заново
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token_youtube.pkl", "wb") as token:
                pickle.dump(creds, token)

    youtube = build("youtube", "v3", credentials=creds)
    return youtube

def get_spotify_tracks(sp, playlist_id, offset=0, limit=50):
    results = sp.playlist_items(playlist_id, offset=offset, limit=limit, fields='items(track(name,artists(name)))')
    tracks = []
    for item in results['items']:
        track = item['track']
        if track:
            track_name = track['name']
            # Проверяем наличие ключа 'artists' и обрабатываем его отсутствие
            if 'artists' in track:
                artist_name = ', '.join([artist['name'] for artist in track['artists']])
                tracks.append(f"{track_name} {artist_name}")
            else:
                print(f"Пропущен трек '{track_name}' из-за отсутствия информации об исполнителе")
    return tracks

def add_to_youtube_playlist(youtube, playlist_id, song_query):
    request = youtube.search().list(
        part="snippet",
        q=song_query,
        maxResults=1
    )
    response = request.execute()
    
    # Проверка на наличие результатов поиска
    if response['items']:
        video_item = response['items'][0]
        # Проверка, существует ли 'id' и 'videoId' в ответе
        if 'id' in video_item and 'videoId' in video_item['id']:
            video_id = video_item['id']['videoId']
            youtube.playlistItems().insert(
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
            ).execute()
        else:
            print(f"Видео не найдено для запроса '{song_query}'.")
    else:
        print(f"Нет результатов поиска для запроса '{song_query}'.")

def main():
    # Аутентификация
    sp = authenticate_spotify()
    youtube = authenticate_youtube()

    # ID плейлиста Spotify и YouTube
    spotify_playlist_id = 'YOUR SPOTIFY_PLAYLIST_ID'
    youtube_playlist_id = 'YOUR_YOUTUBE_PLAYLIST_ID'

    # Получение треков
    offset = 0
    limit = 50
    try:
        with open("progress.json", "r") as f:
            progress = json.load(f)
            offset = progress.get("offset", 0)
    except FileNotFoundError:
        progress = {"offset": 0}

    tracks = get_spotify_tracks(sp, spotify_playlist_id, offset=offset, limit=limit)

    for track in tracks:
        # Вывод информации о переносимом треке
        print(f"Перенос трека: {track}")
        
        add_to_youtube_playlist(youtube, youtube_playlist_id, track)
        offset += 1
        progress["offset"] = offset
        with open("progress.json", "w") as f:
            json.dump(progress, f)

        # Ограничение по количеству запросов
        if offset % 50 == 0:
            print("Достигнут лимит запросов на сегодня, попробуйте снова завтра.")
            break

if __name__ == "__main__":
    main()
