# SubmitResults

## LIMS 

In the custom extensions folder, the contents of this repo is in the submitresults folder. The code is executed in the submit results step of the primary LIMS workflow. LIMS Admin interface, under configuration, process types, submit results step, external programs.

User selects "Proceed" and then "Post". Results are posted to MODX. Email is sent to customer through hubspot, generates supplements file that can be downloaded from LIMS, and if it's a single kit, it hits an endpoint to trigger upgrade trialdate for the modx user. 

## Usage

There are 3 versions of the script here:

i) postresults_v5_test.py - can be used to test the code outside of the EPP triggers by entering the step URI and username, password

ii) postresults_v5.py - runs on the test instance of LIMS

iii) postresults_v5_prod.py - runs on the production instance of LIMS

The 'accessory.py' script is used to test variables.

The 'glsapiutil.py' is the library for the LIMS api

Function:

- posts the result report to the customer's MODX account

- creates a supplement file for customers who are on subscription programs

- triggers the 'upgrade to a subscription' flow by hitting the MODX endpoint