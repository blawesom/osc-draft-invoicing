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
VM_MAP = csv.DictReader(open('vm_types.csv', encoding='utf-8-sig'), delimiter= ';')


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
    # Get Account details
    account_email = get_account(icu_conn)['Account']['Email']
    
    # Catalog is specific to each region
    catalog = get_catalog(icu_conn)   

    # Get Consumption
    with open('draft-invoice.log', 'w+') as log:
        log.write('\nDEBUG: Querying consumption from {} to {} for {} account on {}...'.format(date_range['from_date'], date_range['to_date'], account_email, region))
    conso = get_consumption(icu_conn, date_range)

    # Cross reference entry from consumption with matchin catalog entry and compute cost (quantity x unitprice)
    for line in conso['Entries']:
        if line['Zone'][-1].isalpha():
            line['Zone'] = line['Zone'][:-1]
        invoice_draft.append(generate_invoice_line(account_email, region, line, catalog))
    return invoice_draft

def generate_vm_price(line, region, catalog):

    # if vm type is aws, translate to tinatype structure for price calculation
    if not line.get('Type', '').startswith('BoxUsage:tina'):
        vm_type = line.get('Type').split(':')[1]
        vm_spec = [vm for vm in VM_MAP if vm['name']==vm_type]
        if vm_spec:
            vm_spec=vm_spec[0]
            gen = int(vm_spec['generation'])
            core_count = int(vm_spec['core'])
            ram_count = int(vm_spec['ram/size'])
            perf = int(vm_spec['performance'])
            # TODO: handle GPU
        else:
            with open('draft-invoice.log', 'w+') as log:
                log.write('\nERROR: Unable to compute {} price'.format(vm_type))
            return 0
        
    # vm type is tina type and require parsing
    else:
        # Thx to Heckle for the regex hassle :)
        elements = re.search('tinav(\d).c(\d+)r(\d+)p(\d)', line['Type'])
        gen = int(elements.group(1))
        core_count = int(elements.group(2))
        ram_count = int(elements.group(3))
        perf = int(elements.group(4))
        # not required now that licences are separately billed
        # os_type = re.search('RunInstances-(\d+)-OD', key).group(1)

    for entry in catalog['Entries']:
        if 'RunInstances-OD.CustomCore:v{}-p{}'.format(gen, perf) in entry['Key']:
            core_price = entry['Value']
        elif 'RunInstances-OD.CustomRam' in entry['Key']:
            ram_price = entry['Value']
    unit_price = core_count * core_price + ram_count * ram_price
    return unit_price


def generate_invoice_line(account_email, region, line, catalog):
    # Create line reference for search in catalog
    key = '.'.join(['unitPrice', line['Service'], line['Operation'], line['Type'], line['Zone']])
    for entry in catalog['Entries']:
        key_name = '.'.join([line['Service'], line['Operation'], line['Type']])
        if line.get('Operation', '').startswith('RunInstances-OD'):
            return {'Account': account_email, 'Region': region,'Entry': key_name[7:], 'Quantity': line['Value'],'Cost': line['Value'] * generate_vm_price(line, region, catalog)/1000}
        elif entry['Key']==key:
            return {'Account': account_email, 'Region': region,'Entry': key_name[7:], 'Quantity': line['Value'],'Cost': line['Value'] * entry['Value']/1000}
    with open('draft-invoice.log', 'w+') as log:
        log.write('\nERROR: Entry price for {} do not exist'.format(line['Type']))
    return {'Account': account_email, 'Region': region,'Entry': key_name[7:], 'Quantity': line['Value'],'Cost': 0}


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
        
        with open('draft-invoice.log', 'w+') as log:
            log.write('\nSUCCESS: Account {} from {} to {} => OK'.format(account, from_date, to_date))
    if generate_csv(invoice_draft):
        with open('draft-invoice.log', 'w+') as log:
            log.write('\n\tExport completed from {} to {}: {}\n'.format(from_date, to_date, 'export_{}.csv'.format(TODAY.isoformat())))



def check_arg_dates(args):
    if len(args) > 0:
        dates=[]
        for arg in args:
            try:
                dates.append(datetime.date.fromisoformat(arg))
            except:
                with open('draft-invoice.log', 'w+') as log:
                    log.write('\nERROR: Date Error')
        if len(dates) == 1:
            return args[0], DEFAULT_TO_DATE
        elif dates[0] >= dates[1] or dates[1] >= datetime.date.today():
            with open('draft-invoice.log', 'w+') as log:
                    log.write('\nERROR: Date Error')
            sys.exit(1)
        else:
            return args[0], args[1]
    else:
        return DEFAULT_FROM_DATE, DEFAULT_TO_DATE


if __name__ == '__main__':
    try:
        main(check_arg_dates(sys.argv[1:]))
    except Exception as E:
        with open('draft-invoice.log', 'w+') as log:
            log.write('\n{}'.format(E))

