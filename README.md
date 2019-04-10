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

### Notes

Output is a CSV file with headers and ';' separator.

Note: Default invoicing runs for the active period (1st of the active month up to yesterday).