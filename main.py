
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


def create_draft_bill(icu_conn, invoice_draft):
    # Catalog is specific to each region
    catalog = get_catalog(icu_conn)   
    conso = get_consumption(icu_conn)

    # Cross reference entry from consumption with matchin catalog entry and compute cost (quantity x unitprice)
    for line in conso['Entries']:
        if line['Zone'][-1].isalpha():
            line['Zone'] = line['Zone'][:-1]
        invoice_draft.append(generate_invoice_line(line, catalog))
    return invoice_draft


def generate_invoice_line(line, catalog):
    # Get Account details
    account_email = get_account(icu_conn)['Account']['Email']

    # Create line reference for search in catalog
    key = '.'.join(['unitPrice', line['Service'], line['Operation'], line['Type'], line['Zone']])
    for entry in catalog['Entries']:
        if entry['Key']==key:
            key_name = '.'.join([line['Service'], line['Operation'], line['Type']])
            return {'Account': account_email, 'Region': region,'Entry': key_name[7:], 'Quantity': line['Value'],'Cost': line['Value'] * entry['Value']/1000}


def generate_csv(invoice_draft):
    # account_id / region / item / quantity / cost
    with open('export_{}.csv'.format(TODAY.isoformat()), 'w') as export_csv:
        fields=['Account', 'Region', 'Entry', 'Quantity', 'Cost']
        writer = csv.DictWriter(export_csv, delimiter=';', fieldnames=fields)
        writer.writeheader()
        for item in invoice_draft:
            writer.writerow(item)
    return True


def main():
    catalog = None
    invoice_draft = []

    # Read config file
    config = ConfigParser()
    with open('accounts.cfg') as cnf:
        config.read_file(cnf)

    for account in config.sections():
        # Setup account details
        region = config.get(account, 'region')
        ak = config.get(account, 'ak')
        sk = config.get(account, 'sk')

        icu_conn = IcuCall(access_key=ak, secret_key=sk, region_name=region, host='outscale.com', https=True)

        invoice_draft = create_draft_bill(icu_conn, invoice_draft)

        print('Account: {}  => OK'.format(account))

    if generate_csv(invoice_draft):
        print('\n\tExport completed from {} to {}: {}\n'.format(DEFAULT_FROM_DATE, DEFAULT_TO_DATE, 'export_{}.csv'.format(TODAY.isoformat())))


if __name__ == '__main__':
    main()