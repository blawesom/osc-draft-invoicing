
import sys
import csv
import json
import datetime
from sdk import IcuCall
from configparser import ConfigParser


TODAY=datetime.date.today()
YESTERDAY=TODAY - datetime.timedelta(days=1)
DEFAULT_FROM_DATE=datetime.date(TODAY.year, TODAY.month, 1).isoformat()
DEFAULT_TO_DATE=YESTERDAY.isoformat()


def get_account(icu_conn):
    icu_conn.make_request(call='GetAccount')
    return icu_conn.response


def get_catalog(icu_conn):
    icu_conn.make_request(call='ReadPublicCatalog')
    return icu_conn.response['Catalog']


def get_consumption(icu_conn, from_date=DEFAULT_FROM_DATE, to_date=DEFAULT_TO_DATE):
    icu_conn.make_request(call='ReadConsumptionAccount', FromDate=from_date, ToDate=to_date)
    return icu_conn.response


def main():
    catalog = None
    invoice_draft = []

    # Read config file
    config = ConfigParser()
    with open('accounts.cfg') as cnf:
        config.read_file(cnf)

    accounts = config.sections()

    for account in accounts:
        # Setup account details
        region = config.get(account, 'region')
        ak = config.get(account, 'ak')
        sk = config.get(account, 'sk')

        icu_conn = IcuCall(access_key=ak, secret_key=sk, region=region, host='outscale.com')
        account_email = get_account(icu_conn)['Account']['Email']

        # Pull catalog once
        if not catalog:
            catalog = get_catalog(icu_conn)
            
        conso = get_consumption(icu_conn)

        # Cross reference entry from consumption with matchin catalog entry and compute cost (quantity x unitprice)
        for line in conso['Entries']:
            if line['Zone'][-1].isalpha():
                line['Zone'] = line['Zone'][:-1]
            key = '.'.join(['unitPrice', line['Service'], line['Operation'], line['Type'], line['Zone']])
            for entry in catalog['Entries']:
                if entry['Key']==key:
                    key_name = '.'.join([line['Service'], line['Operation'], line['Type']])
                    invoice_draft.append({'Account': account_email, 'Region': region,'Entry': key_name[7:], 'Quantity': line['Value'],'Cost': line['Value'] * entry['Value']/1000})
                    break

    # Output format in csv
    # account_id / region / item / quantity / cost
    with open('export_{}.csv'.format(TODAY.isoformat()), 'w') as export_csv:
        fields=['Account', 'Region', 'Entry', 'Quantity', 'Cost']
        writer = csv.DictWriter(export_csv, delimiter=';', fieldnames=fields)
        
        writer.writeheader()
        for item in invoice_draft:
            writer.writerow(item)
    
    print('\n\tExport completed from {} to {}: {}\n'.format(DEFAULT_FROM_DATE, DEFAULT_TO_DATE, 'export_{}.csv'.format(TODAY.isoformat())))

if __name__ == '__main__':
    main()