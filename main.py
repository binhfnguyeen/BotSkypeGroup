from skpy import Skype, SkypeMsg, SkypeSingleChat, SkypeGroupChat
from datetime import datetime, timedelta
import gspread
import pandas as pd
from google.auth import default
import json
import pytz
import re
import os

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
SKYPE_GROUP_ID = os.getenv("SKYPE_GROUP_ID")
SKYPE_GROUP_ID2 = os.getenv("SKYPE_GROUP_ID2")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")


def convert_time(time):
    return time + timedelta(hours=7)  #Convert to GMT+7


# Fix <e_m></e_m>
def clean_message(content):
    return re.sub(r"<[^>]+>", "", content)


def update_spreadsheet(df, sheet_name, spreadsheet_url=None):
    if spreadsheet_url is None:
        spreadsheet_url = GOOGLE_SHEET_URL

    service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT)
    gc = gspread.service_account_from_dict(service_account_info)
    
    google_sheet = gc.open_by_url(spreadsheet_url)
    # print('sheetname',sheetname)

    try:
        sh = google_sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        sh = google_sheet.add_worksheet(title=sheet_name, rows=1000, cols=10)

    # Lấy toàn bộ dữ liệu của sheets
    existing_data = sh.get_all_values()

    # Nếu chưa có dữ liệu thì thêm mới
    if not existing_data:
        sh.update(values=[df.columns.values.tolist()] + df.values.tolist())
        return
    # Chuyển dữ liệu hiện tại thành data frame
    existing_df = pd.DataFrame(existing_data[1:], columns=existing_data[0]) # Bỏ dòng header

    # Chuyển dữ liệu thành string để so sánh
    existing_df['DATETIME'] = existing_df['DATETIME'].astype('string')

    # Lọc dữ liệu chưa có trong sheets
    new_df = df[~df['DATETIME'].isin(existing_df['DATETIME'])]

    if not new_df.empty:
        index_first_empty_row = len(existing_data)+1 # Lấy vị trí dòng chưa có dữ liệu
        end_index = index_first_empty_row+new_df.shape[0]-1 
        sh.update( range_name=f'A{index_first_empty_row}:D{end_index}', values=new_df.values.tolist())
        print(f"Đã thêm {len(new_df)} dòng dữ liệu mới.")
    else:
        print("Không có dữ liệu mới để thêm.")


group_topic = ""
print('Login success')
cur_date = datetime.today()


def get_group_message(group_id, num_day=2, sorted=False, update=False):
    """
        Get messages in the specified group within the last 'num_day' days.
        If 'sorted' is True, the messages will be sorted in ascending order of datetime.
        If 'update' is True, the data will be updated in Google Sheet.
    """

    sk = Skype(USERNAME, PASSWORD)
    if group_id is None:
        group_id = SKYPE_GROUP_ID

    channel = sk.chats[group_id]
    group_topic = channel.topic
    sheet_name = group_topic[:2]
    print('Group topic: ', group_topic)

    date_temp = cur_date
    date_previous = (date_temp - timedelta(days=num_day)).replace(hour=0, minute=0, second=0)
    list_message = []
    #get all msg within num_day
    while date_temp >= date_previous:
        print('date temp', date_temp)
        msgs = channel.getMsgs()
        if msgs is None or len(msgs) == 0:
            break
        list_message += msgs

        date_temp = convert_time(list_message[-1].time)
        print('Date_temp after conver', date_temp)

    df_data = pd.DataFrame(columns=['USERID', 'DATETIME', 'NAME', 'CONTENT'])
    for idx, message in enumerate(list_message):
        message_time = convert_time(message.time)
        print('msg content: ', message.content, ' date: ', message.time)
        if (message_time >= date_previous) and (message_time < date_previous + timedelta(days=num_day + 1)):
            df_data.loc[idx, 'USERID'] = message.userId
            df_data.loc[idx, 'DATETIME'] = convert_time(message.time).strftime('%Y-%m-%d %H:%M:%S')
            df_data.loc[idx, 'NAME'] = message.user.name
            df_data.loc[idx, 'CONTENT'] = message.content
        else:
            print("time not valid")

    if sorted is True:
        df_data = df_data.sort_values('DATETIME')

    # Convert all columns' dtypes to string
    df_data['DATETIME'] = df_data['DATETIME'].astype('string')
    df_data['NAME'] = df_data['NAME'].astype('string')
    df_data['CONTENT'] = df_data['CONTENT'].astype('string')
    df_data['USERID'] = df_data['USERID'].astype('string')
    df_data['CONTENT'] = df_data['CONTENT'].apply(clean_message)

    # Filter out rows that are not messages created by users
    df_data = df_data[~df_data['CONTENT'].str.startswith('<')]

    if update is True:
        update_spreadsheet(df=df_data, sheet_name=sheet_name)

    return df_data

if __name__ == '__main__':
    df = get_group_message(group_id=SKYPE_GROUP_ID, num_day=1, sorted=True, update=True)
    df2 = get_group_message(group_id=SKYPE_GROUP_ID2, num_day=1, sorted=True, update=True)
    df
    df2