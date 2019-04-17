import re
import sys
import csv
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


def get_consumption(icu_conn, date_range):
    icu_conn.make_request(call='ReadConsumptionAccount', FromDate=date_range['from_date'], ToDate=date_range['to_date'])
    return icu_conn.response


def create_draft_bill(icu_conn, region, invoice_draft, date_range):
    # Catalog is specific to each region
    catalog = get_catalog(icu_conn)   
    conso = get_consumption(icu_conn, date_range)
    
    # Get Account details
    account_email = get_account(icu_conn)['Account']['Email']

    # Cross reference entry from consumption with matchin catalog entry and compute cost (quantity x unitprice)
    for line in conso['Entries']:
        if line['Zone'][-1].isalpha():
            line['Zone'] = line['Zone'][:-1]
        invoice_draft.append(generate_invoice_line(account_email, region, line, catalog))
    return invoice_draft


def generate_tinatype_price(line, region, catalog):
    # Thx to Heckle for the regex hassle :)
    elements = re.search('tina(.*).c(\d+)r(\d+)', line['Type'])
    # gen = int(elements(1))
    core_count = int(elements.group(2))
    ram_count = int(elements.group(3))
    os_type = re.search('RunInstances-(\d+)-OD', line['Type']).group(1)
    for entry in catalog['Entries']:
        if entry['Key'] == 'detailPrice.TinaOS-FCU.RunInstances-{}-OD.Custom{}'.format(os_type, 'Core'):
            core_price = entry['Value']
        elif entry['Key'] == 'detailPrice.TinaOS-FCU.RunInstances-{}-OD.Custom{}'.format(os_type, 'Ram'):
            ram_price = entry['Value']
    unit_price = core_count * core_price + ram_count * ram_price
    return unit_price


def generate_invoice_line(account_email, region, line, catalog):
    # Create line reference for search in catalog
    key = '.'.join(['unitPrice', line['Service'], line['Operation'], line['Type'], line['Zone']])
    for entry in catalog['Entries']:
        if entry['Key']==key:
            key_name = '.'.join([line['Service'], line['Operation'], line['Type']])
            return {'Account': account_email, 'Region': region,'Entry': key_name[7:], 'Quantity': line['Value'],'Cost': line['Value'] * entry['Value']/1000}
        elif line.get('Type', '').startswith('BoxUsage:tina'):
            return {'Account': account_email, 'Region': region,'Entry': key_name[7:], 'Quantity': line['Value'],'Cost': line['Value'] * generate_tinatype_price(line, region, catalog)/1000}
        # else:
        #     print('Entry price for {} not determined'.format(entry['Key']))


def generate_csv(invoice_draft):
    # account_id / region / item / quantity / cost
    with open('export_{}.csv'.format(TODAY.isoformat()), 'w') as export_csv:
        fields=['Account', 'Region', 'Entry', 'Quantity', 'Cost']
        writer = csv.DictWriter(export_csv, delimiter=';', fieldnames=fields)
        writer.writeheader()
        for item in invoice_draft:
            writer.writerow(item)
    return True


def main(dates):
    from_date, to_date = dates[0:2]
    catalog = None
    invoice_draft = []
    date_range = {'from_date': from_date,
                  'to_date': to_date}

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

        invoice_draft = create_draft_bill(icu_conn, region, invoice_draft, date_range)

        print('Account: {} from {} to {} => OK'.format(account, from_date, to_date))

    if generate_csv(invoice_draft):
        print('\n\tExport completed from {} to {}: {}\n'.format(DEFAULT_FROM_DATE, DEFAULT_TO_DATE, 'export_{}.csv'.format(TODAY.isoformat())))


def check_arg_dates(args):
    if len(args) > 0:
        dates=[]
        for arg in args:
            try:
                dates.append(datetime.date.fromisoformat(arg))
            except:
                print('Date error')
        if len(dates) == 1:
            return args[0], DEFAULT_TO_DATE
        elif dates[0] <= dates[1] or dates[1] >= datetime.date.today.isoformat():
            print('Date error')
            sys.exit(1)
        else:
            return args[0], args[1]
    else:
        return DEFAULT_FROM_DATE, DEFAULT_TO_DATE


if __name__ == '__main__':
    
    main(check_arg_dates(sys.argv[1:]))