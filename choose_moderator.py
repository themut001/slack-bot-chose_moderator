import os
import random
from datetime import datetime, timedelta

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- 設定 ---

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]
MEMBERS = os.environ["MEMBER_IDS"].split(",")  # 例: "U01AAA,U02BBB,U03CCC"

# スプレッドシートのID（URLの/d/〜/edit の部分）
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME = "moderators"

# 祝日カレンダーID（日本）
HOLIDAY_CALENDAR_ID = "ja.japanese#holiday@group.v.calendar.google.com"

# --- Google 認証 ---

credentials = service_account.Credentials.from_service_account_file(
    "google_calendar_credentials.json",
    scopes=[
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
)
calendar_service = build("calendar", "v3", credentials=credentials)
sheets_service = build("sheets", "v4", credentials=credentials)

# --- Slack クライアント ---

slack_client = WebClient(token=SLACK_BOT_TOKEN)

# --- 祝日判定 ---

def is_japanese_holiday():
    today = datetime.utcnow() + timedelta(hours=9)  # JST
    iso_date = today.date().isoformat()

    events = calendar_service.events().list(
        calendarId=HOLIDAY_CALENDAR_ID,
        timeMin=f"{iso_date}T00:00:00+09:00",
        timeMax=f"{iso_date}T23:59:59+09:00",
        singleEvents=True
    ).execute()

    return len(events.get("items", [])) > 0

# --- ユーザー名取得 ---

def get_user_name(user_id):
    try:
        print(f"ユーザーID {user_id} の情報を取得中...")
        response = slack_client.users_info(user=user_id)
        user_info = response["user"]
        
        # display_nameがあればそれを使用、なければreal_nameを使用
        display_name = user_info.get("profile", {}).get("display_name")
        real_name = user_info.get("real_name")
        
        result_name = display_name if display_name else real_name
        print(f"取得したユーザー名: {result_name}")
        return result_name
        
    except SlackApiError as e:
        print(f"ユーザー情報取得エラー: {e.response['error']}")
        # エラー時はユーザーIDをそのまま返す（メンション形式ではなく）
        return user_id

# --- Slack通知 ---

def post_to_slack(user_id):
    message = f":bell: 明日の朝会（9:00～）の進行役は <@{user_id}> さんです！よろしくお願いします！"
    try:
        slack_client.chat_postMessage(channel=CHANNEL_ID, text=message)
        print("Slack通知を送信しました。")
    except SlackApiError as e:
        print(f"Slackエラー: {e.response['error']}")

# --- Google Sheets記録 ---

def log_to_google_sheets(user_id, user_name):
    today = datetime.utcnow() + timedelta(hours=9)
    print(f"スプレッドシートに記録: 日付={today.strftime('%Y/%m/%d')}, ユーザー名={user_name}")
    
    values = [[
        today.strftime("%Y/%m/%d"),
        user_name,  # ユーザー名を記録
        today.strftime("%A")
    ]]

    body = {"values": values}
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    print("Google Sheetsに記録しました。")

# --- メイン処理 ---

def main():
    today = datetime.utcnow() + timedelta(hours=9)  # JST
    if today.weekday() >= 5:
        print("土日なのでスキップ")
        return
    if is_japanese_holiday():
        print("日本の祝日なのでスキップ")
        return

    selected_user = random.choice(MEMBERS)
    print(f"選択されたユーザーID: {selected_user}")
    
    user_name = get_user_name(selected_user)
    print(f"最終的なユーザー名: {user_name}")
    
    post_to_slack(selected_user)
    log_to_google_sheets(selected_user, user_name)

if __name__ == "__main__":
    main()
