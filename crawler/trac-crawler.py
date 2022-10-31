#!/usr/bin/env python
import os
from os import environ
from time import sleep
from tracbot import get_ticket_comments, return_timestrings, TracBot, trac_to_json


def main():
    trac_path = environ['TRAC_PATH'] if 'TRAC_PATH' in environ else ''
    cred = environ['CREDENTIAL'] if 'CREDENTIAL' in environ else ''
    ticket_ids = environ['TICKET_IDS'].split(
        ',') if 'TICKET_IDS' in environ else []
    keywords = environ['KEYWORDS'].split(
        ',') if 'KEYWORDS' in environ else []  # environ['TZ'] = 'Asia/Taipei'
    tracbot = TracBot(trac_path, cred)

    for keyword in keywords:
        ticket_ids += tracbot.get_ticket_id_by_keyword(keyword)

    ticket_ids = [int(i) for i in ticket_ids]
    ticket_ids = list(dict.fromkeys(ticket_ids))

    for ticket_id in ticket_ids:
        link = None
        author = None
        ticket_comments = None
        ticket_attachments = []
        ticket_data = tracbot.get_ticket(ticket_id)
        if len(ticket_data) == 0:
            continue

        for _ in range(5):
            ticket_comments = get_ticket_comments(trac_path, cred, ticket_id)
            if ticket_comments is not None:
                break
            sleep(1)

        for ticket_comment in ticket_comments:
            if ticket_comment['timestamp'] == ticket_data['changetime']:
                link = ticket_comment['link']
                author = ticket_comment['dc_creator']
                break

        if author is None:
            author = ticket_data['reporter']

        ticket_data['ticket_id'] = ticket_id
        ticket_data['comments'] = ticket_comments

        folder_name = f"{ticket_id}_{ticket_data['reporter']}_{ticket_data['summary']}"
        export_path = os.path.join(
            "export",
            ticket_data['status'],
            folder_name)
        os.makedirs(export_path, exist_ok=True)

        for _ in range(5):
            ticket_attachments = tracbot.list_attachment(ticket_id)
            if ticket_attachments is not None:
                break
            sleep(1)

        for attachment in ticket_attachments:
            tracbot.download_attachment(ticket_id, attachment, export_path)

        trac_to_json(ticket_data, export_path)

        date_str, time_str = return_timestrings(ticket_data['changetime'])
        output_str = '\033[1;30m{0} '.format(date_str)
        output_str += '\033[0m{0} '.format(time_str)
        output_str += '#{0} '.format(ticket_id)
        output_str += '(by \033[32m{0}\033[0m) '.format(author)
        output_str += ticket_data['summary']
        output_str += ' \033[33m{0}\033[0m'.format(link)
        print(output_str)


if __name__ == '__main__':
    main()
