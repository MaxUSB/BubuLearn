import re
import sys
import json
import requests
from datetime import datetime, timedelta


class BubuLearn:
    def __init__(self, config):
        self.email = config['email']
        self.password = config['password']
        self.user_id = config['user_id']
        self.product_ids = config['product_ids']
        self.cookies = {}
        self.__login()
        self.events = self.__get_events()
        self.customers = {}
        self.students = {}
        for p_id in self.product_ids:
            self.customers[p_id] = self.__get_customers(p_id)
            self.students[p_id] = self.__get_students(p_id)

    def __login(self):
        res = requests.get('http://backofficestage.bubulearn.com')
        self.cookies['XSRF-TOKEN'] = res.cookies['XSRF-TOKEN']
        self.cookies['crm_session'] = res.cookies['crm_session']
        token = re.search('<meta name="csrf-token" content="([\w\d]+)">', res.text).group(1)
        payload = f'email={self.email}&password={self.password}&_token={token}'
        res = requests.post('http://backofficestage.bubulearn.com/login', data=payload, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': f'XSRF-TOKEN={self.cookies["XSRF-TOKEN"]}; crm_session={self.cookies["crm_session"]}'
        })
        self.cookies['XSRF-TOKEN'] = res.cookies['XSRF-TOKEN']
        self.cookies['crm_session'] = res.cookies['crm_session']

    def logout(self):
        requests.get('http://backofficestage.bubulearn.com/logout', headers={
            'Cookie': f'XSRF-TOKEN={self.cookies["XSRF-TOKEN"]}; crm_session={self.cookies["crm_session"]}'
        })
        self.cookies = {}

    def __get_events(self):
        res = requests.get(
            f'http://backofficestage.bubulearn.com/api/calendars/events?filter[user_id]={self.user_id}&filter[started_after]={(datetime.now() - timedelta(14)).strftime("%Y-%m-%dT00:00:00")}',
            headers={
                'Cookie': f'XSRF-TOKEN={self.cookies["XSRF-TOKEN"]}; crm_session={self.cookies["crm_session"]}'
            })
        self.cookies['XSRF-TOKEN'] = res.cookies['XSRF-TOKEN']
        self.cookies['crm_session'] = res.cookies['crm_session']
        return res.json()['events']

    def __get_customers(self, product_id):
        res = requests.get(f'http://backofficestage.bubulearn.com/api/customers?filter[has_user]={self.user_id},{product_id}&include=phones', headers={
            'Cookie': f'XSRF-TOKEN={self.cookies["XSRF-TOKEN"]}; crm_session={self.cookies["crm_session"]}'
        })
        self.cookies['XSRF-TOKEN'] = res.cookies['XSRF-TOKEN']
        self.cookies['crm_session'] = res.cookies['crm_session']
        customers = res.json()['data']
        phones = list(map(lambda x: x['phones'][0]['phone'], customers))
        return {phone: customers[i] for i, phone in enumerate(phones)}

    def __get_students(self, product_id):
        res = requests.get(f'http://backofficestage.bubulearn.com/api/students?filter[has_user]={self.user_id},{product_id}', headers={
            'Cookie': f'XSRF-TOKEN={self.cookies["XSRF-TOKEN"]}; crm_session={self.cookies["crm_session"]}'
        })
        self.cookies['XSRF-TOKEN'] = res.cookies['XSRF-TOKEN']
        self.cookies['crm_session'] = res.cookies['crm_session']
        students = res.json()['students']
        customer_ids = list(map(lambda x: x['customer_id'], students))
        return {customer_id: students[i] for i, customer_id in enumerate(customer_ids)}

    def drop_duplicates_events(self, events):
        new_events = []
        exist_dates = list(map(lambda x: x['start'], self.events))
        for event in events:
            if event['date'].strftime('%Y-%m-%d %H:%M') not in exist_dates:
                new_events.append(event)
        return new_events

    def add_event(self, phone, date):
        product_id = self.product_ids[0]
        customer = None
        for p_id in self.product_ids:
            customer = self.customers[p_id].get(phone)
            if customer is not None:
                product_id = p_id
                break
        student = self.students[product_id].get(customer['id']) if customer is not None else None
        if customer is not None and student is not None:
            customer['phone'] = phone
            payload = {
                "id": None,
                "product_id": product_id,
                "skip_reason_id": None,
                "is_repeatable": False,
                "comment": "",
                "is_diagnostic": False,
                "is_paid": True,
                "product": {
                    "id": 0,
                    "unique_name": "",
                    "name": ""
                },
                "user_id": self.user_id,
                "start": date.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                "end": (date + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                "customer_id": customer['id'],
                "customer": customer,
                "student_id": student['id'],
                "student": student,
            }
            res = requests.post('http://backofficestage.bubulearn.com/api/calendars/events/add', data=json.dumps(payload), headers={
                'Content-type': 'application/json',
                'Cookie': f'XSRF-TOKEN={self.cookies["XSRF-TOKEN"]}; crm_session={self.cookies["crm_session"]}',
                'X-XSRF-TOKEN': self.cookies["XSRF-TOKEN"].replace('%3D', '=')
            })
            self.cookies['XSRF-TOKEN'] = res.cookies['XSRF-TOKEN']
            self.cookies['crm_session'] = res.cookies['crm_session']
            return res.status_code == 200 and res.json()['event']['id'] is not None
        else:
            return False


class ICSParser:
    def __init__(self, file):
        self.file = open(file, 'r')

    def get_events(self, is_current_week=True):
        split_text = self.file.read().split('BEGIN:VEVENT')[1:]
        all_events = list(map(lambda x: {
            'phone': re.search('SUMMARY:[^\d]+(\+[\d ]+)', x).group(1).replace(" ", ""),
            'date': datetime.strptime(re.search('DTSTART:([\dTZ]+)\n', x).group(1), '%Y%m%dT%H%M%SZ') + timedelta(hours=3),
        }, split_text))
        events = []
        min_date = datetime.now().date()
        max_date = min_date
        while min_date.weekday() != 0:
            min_date -= timedelta(1)
        while max_date.weekday() != 0 or max_date == min_date:
            max_date += timedelta(1)
        if not is_current_week:
            min_date -= timedelta(days=7)
            max_date -= timedelta(days=7)
        for event in all_events:
            if min_date <= event['date'].date() < max_date:
                events.append(event)
        return events


def run(file_path):
    bl = None
    try:
        print('загрузка данных...', end=' ')
        config = json.loads(open('config.json', "r").read())
        print('готово.\nзагрузка уроков из файла...', end=' ')
        ics_p = ICSParser(file_path)
        events = ics_p.get_events()
        print('готово.\nподключение к BubuLearn...', end=' ')
        bl = BubuLearn(config)
        print('готово.\nудаление дублирующихся уроков...', end=' ')
        events = bl.drop_duplicates_events(events)
        print('готово.\nдобавление уроков...', end=' ')
        for event in events:
            success = bl.add_event(event['phone'], event['date'])
            if not success:
                print(f"\nУрок на {event['date'].strftime('%d.%m.%Y %H:%M:%S')} для {event['phone']} не удалось добавить!", file=sys.stderr)
        print('готово.')
    except Exception as e:
        print(f'ошибка: {e}', file=sys.stderr)
    finally:
        print('выход из системы...', end=' ')
        if bl is not None:
            bl.logout()
        print('готово.')


if __name__ == '__main__':
    run('~/Desktop/test.ics')
