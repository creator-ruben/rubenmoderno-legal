#!/usr/bin/env python3
"""
TikTok Video Upload Script
Uses TikTok Content Posting API v2 (push_by_file method).

Usage:
    python tiktok_upload.py --auth-code CODE --video path/to/video.mp4 --title "My Video"

Or if you already have an access token:
    python tiktok_upload.py --token TOKEN --video path/to/video.mp4 --title "My Video"
"""

import argparse
import json
import os
import sys
import requests

CREDENTIALS_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '.credentials', 'tiktok_credentials.json'
)


def load_credentials():
    with open(CREDENTIALS_PATH) as f:
        return json.load(f)


def exchange_code_for_token(client_key, client_secret, code, redirect_uri):
    """Exchange authorization code for access token."""
    resp = requests.post(
        'https://open.tiktokapis.com/v2/oauth/token/',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'client_key': client_key,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if 'access_token' not in data:
        print(f"Token exchange failed: {data}", file=sys.stderr)
        sys.exit(1)
    print(f"Access token obtained. Expires in {data.get('expires_in', '?')}s")
    return data['access_token']


def init_upload(access_token, video_size):
    """Initialize a file upload and get the upload URL."""
    resp = requests.post(
        'https://open.tiktokapis.com/v2/post/publish/inbox/video/init/',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=UTF-8',
        },
        json={
            'source_info': {
                'source': 'FILE_UPLOAD',
                'video_size': video_size,
                'chunk_size': video_size,
                'total_chunk_count': 1,
            },
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('error', {}).get('code') != 'ok':
        print(f"Init upload failed: {data}", file=sys.stderr)
        sys.exit(1)
    publish_id = data['data']['publish_id']
    upload_url = data['data']['upload_url']
    print(f"Upload initialized. publish_id={publish_id}")
    return publish_id, upload_url


def upload_video_file(upload_url, video_path, video_size):
    """Upload the video file to TikTok's upload URL."""
    with open(video_path, 'rb') as f:
        resp = requests.put(
            upload_url,
            headers={
                'Content-Type': 'video/mp4',
                'Content-Length': str(video_size),
                'Content-Range': f'bytes 0-{video_size - 1}/{video_size}',
            },
            data=f,
        )
    resp.raise_for_status()
    print("Video uploaded successfully.")


def publish_video(access_token, publish_id, title, description='',
                  privacy='SELF_ONLY', disable_comment=False, disable_duet=False):
    """Publish the uploaded video."""
    resp = requests.post(
        'https://open.tiktokapis.com/v2/post/publish/video/init/',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=UTF-8',
        },
        json={
            'post_info': {
                'title': title,
                'description': description,
                'privacy_level': privacy,
                'disable_comment': disable_comment,
                'disable_duet': disable_duet,
            },
            'source_info': {
                'source': 'PULL_FROM_URL',
                'video_url': '',  # not needed for FILE_UPLOAD
            },
        },
    )
    # Note: For FILE_UPLOAD flow, publishing happens automatically after upload.
    # The publish_id from init is used to track status.
    print(f"Video publish initiated. publish_id={publish_id}")
    return publish_id


def check_status(access_token, publish_id):
    """Check the publish status of a video."""
    resp = requests.post(
        'https://open.tiktokapis.com/v2/post/publish/status/fetch/',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=UTF-8',
        },
        json={'publish_id': publish_id},
    )
    resp.raise_for_status()
    data = resp.json()
    status = data.get('data', {}).get('status', 'UNKNOWN')
    print(f"Publish status: {status}")
    return data


def main():
    parser = argparse.ArgumentParser(description='Upload video to TikTok')
    parser.add_argument('--auth-code', help='OAuth authorization code')
    parser.add_argument('--token', help='Access token (skip code exchange)')
    parser.add_argument('--video', required=True, help='Path to video file')
    parser.add_argument('--title', required=True, help='Video title')
    parser.add_argument('--description', default='', help='Video description')
    parser.add_argument('--privacy', default='SELF_ONLY',
                        choices=['PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS',
                                 'FOLLOWER_OF_CREATOR', 'SELF_ONLY'],
                        help='Privacy level (default: SELF_ONLY)')
    args = parser.parse_args()

    if not args.token and not args.auth_code:
        print("Provide either --auth-code or --token", file=sys.stderr)
        sys.exit(1)

    creds = load_credentials()
    access_token = args.token

    if not access_token:
        access_token = exchange_code_for_token(
            creds['client_key'], creds['client_secret'],
            args.auth_code, creds['redirect_uri'],
        )

    video_size = os.path.getsize(args.video)
    print(f"Video: {args.video} ({video_size} bytes)")

    publish_id, upload_url = init_upload(access_token, video_size)
    upload_video_file(upload_url, args.video, video_size)
    check_status(access_token, publish_id)
    print("\nDone! Video is being processed by TikTok.")


if __name__ == '__main__':
    main()
