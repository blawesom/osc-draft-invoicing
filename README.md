# Outscale Draft Invoicing Tool

## Warnings

*Requires Python 3.5*

Tool based on public CLI code available here: https://github.com/outscale/osc-cli

This tool or its output do not bind the provider or Outscale to the effective bills emitted by Outscale.

## How to

1. Configure your *accounts.cfg* with all your accounts details and put it in this root folder
2. Setup environment:
    > python3 -m venv venv

    > source venv/bin/activate

    > python3 -m pip install -r requirements.txt
3. Launch draft invoicing:
    > python3 main.py
4. Customize date range with:
    > python3 main.py 2019-01-01 2019-03-31

If no date is provided, default date range is from the first day of the month, to yesterday. If only one date is provided, date range is from this date to yesterday.

### Notes

Output is a CSV file with headers and ';' separator.