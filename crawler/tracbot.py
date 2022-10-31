#!/usr/bin/env python3
import json
import requests
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from time import time
from xmlrpc.client import Fault, MultiCall, ServerProxy
from base64 import b64decode

XMLRPC_HEADER = [
    ("Host", "issue.kkinternal.com"),
    ("Accept", "application/xml"),
    ("User-Agent", "kkboxsabot/1.0"),
    ("Content-Type", "application/xml")
]


def return_timestamp(dt_obj):
    if isinstance(dt_obj, str):
        if len(dt_obj) > 11:
            # pubDate
            # example 'Thu, 20 Jan 2022 02:34:51 GMT'
            fmt_str = r'%a, %d %b %Y %H:%M:%S %Z'
        else:
            # duedate
            # example '2022-03-31'
            fmt_str = r'%Y-%m-%d'
        dt_obj = datetime.strptime(dt_obj, fmt_str)
    return int(round(dt_obj.timestamp()))


def return_timestrings(timestamp):
    dt_obj = datetime.fromtimestamp(timestamp) + timedelta(hours=8)
    date_str = dt_obj.strftime(r'%Y-%m-%d')
    time_str = dt_obj.strftime(r'%H:%M')
    return [date_str, time_str]


def decode_cred(credential):
    return b64decode(credential).decode('utf-8')


def get_ticket_comments(trac_path, credential, trac_id):
    trac_url = 'https://{0}/ticket/{1}'.format(trac_path, trac_id)
    authinfo = tuple(decode_cred(credential).split(':'))
    payload = {'format': 'rss'}
    response = requests.get(trac_url, auth=authinfo, params=payload)
    comments = []
    if response.ok:
        response_txt = response.text.replace('dc:creator', 'dc_creator')
        root = ET.fromstring(response_txt)
        for item in root.find('channel').findall('item'):
            comment = {
                'pubDate': item.find('pubDate').text,
                'title': item.find('title').text,
                'link': item.find('link').text,
                'guid': item.find('guid').text,
                'description': item.find('description').text,
                'category': item.find('category').text,
            }
            if item.find('dc_creator') is None:
                comment['dc_creator'] = ''
            else:
                comment['dc_creator'] = item.find('dc_creator').text
            comment['timestamp'] = return_timestamp(comment['pubDate'])
            comments.append(comment)
        response.close()
        return comments
    else:
        print('Cannot get comments!')
        response.close()
        return None


class TracBot:
    def __init__(self, trac_path, credential):
        self.trac_path = trac_path
        self.credential = credential
        self.proxy = None
        self.multicall = None
        self._create_proxy()

    def _create_proxy(self):
        self.proxy = ServerProxy(
            'https://{0}@{1}/xmlrpc'.format(
                decode_cred(self.credential), self.trac_path),
            use_datetime=True,
            headers=XMLRPC_HEADER
        )
        self.multicall = MultiCall(self.proxy)

    def _fix_duedate(self, duedate):
        items = duedate.split('-')
        for ind in range(1, 3):
            if len(items[ind]) < 2:
                items[ind] = '0' + items[ind]
        ret_value = '-'.join(items)
        if len(ret_value) == 8:
            ret_value = datetime.strptime(
                ret_value, r'%m-%d-%y').strftime(r'%Y-%m-%d')
        return ret_value

    def get_ticket(self, trac_id):
        ticket_row = {}
        try:
            content = self.proxy.ticket.get(trac_id)
        except Fault:
            return ticket_row
        ticket_row = content[3]

        for col in ['time', 'changetime']:
            if col in ticket_row:
                dt_obj = ticket_row[col]
                ticket_row[col] = return_timestamp(dt_obj)

        ticket_row.pop('_ts', None)

        if 'duedate' in ticket_row and '' != ticket_row['duedate']:
            if len(ticket_row['duedate']) != 10:
                ticket_row['duedate'] = self._fix_duedate(
                    ticket_row['duedate'])
            ticket_row['duedate_ts'] = return_timestamp(ticket_row['duedate'])
        else:
            if 'time' in ticket_row:
                ticket_row['duedate'] = None
                ticket_row['duedate_ts'] = None

        ticket_row['link'] = 'https://{0}/ticket/{1}'.format(
            self.trac_path, trac_id)
        return ticket_row

    def get_ticket_id_by_keyword(self, keyword=None):
        ticket_id_list = None
        if keyword is not None:
            ticket_id_list = self.proxy.ticket.query(
                f"keywords=~{keyword}&max=0")

        return ticket_id_list

    def list_attachment(self, trac_id):
        ticket_attachments = []
        try:
            content = self.proxy.ticket.listAttachments(trac_id)
        except Fault:
            return ticket_attachments

        for attachment in content:
            ticket_attachments.append(attachment[0])

        return ticket_attachments

    def get_attachment(self, trac_id, filename):
        try:
            content = self.proxy.ticket.getAttachment(trac_id, filename)
        except Fault as e:
            print(e)

        return content

    def download_attachment(self, trac_id, filename, export_path):
        save_path = os.path.join(export_path, "files")
        os.makedirs(save_path, exist_ok=True)
        url = 'https://{0}/raw-attachment/ticket/{1}/{2}'.format(
            self.trac_path,
            trac_id,
            filename)
        authinfo = tuple(decode_cred(self.credential).split(':'))

        try:
            response = requests.get(url, auth=authinfo)

            with open(f"{save_path}/{filename}", mode="wb") as f:
                f.write(response.content)
        except Exception as e:
            print(e)


def trac_to_json(data, export_path):
    # Serializing json
    json_obj = json.dumps(data, indent=2, ensure_ascii=False)

    # Writing to file
    with open(f"{export_path}/ticket.json", "w") as outfile:
        outfile.write(json_obj)
