## The purpose of this script is to post results to a customer's account on MODX
## The script also sends a notification email to the customer that their results are ready

## The script also generates a supplement file for the customers on the Ixcela Complete program to be uploaded to
## the Makers portal - THIS SHOULD BE CHANGED TO USING THE MAKERS API

## The decision to post results to a customer's account is based on the value of the ResultFile UDF 'Next Steps', which
## can either be 'Proceed' or 'Stop'

"""
06/12/2019
Edits:
1) For 'Assess' customers - hit the MODX endpoint that will display the 'Upgrade' button on the user account to upgrade
to Ixcela Complete
2) Modify logic to account for new product names when making supplement file - i.e. 'Monthly Subscription', 'Complete',
and all the Pro subscriptions
3) Modify order of fields during supplement file creation - add 'curradd[0]' (corresponds to 'Company' if present or '')
before 'currfname', which is the customer name and is a required field

08/29/19
Edits:
1) Add 'Ixcela FX' to plan type list that receive supplements
2) Change 'Biome Support/ #3' supplement number of bottles from 4 to 1 (as each bottle is now a 3 mo supply)
"""

import glsapiutil
from xml.dom.minidom import parseString
from optparse import OptionParser
import requests
from datetime import date, datetime
import json
from email.mime.text import MIMEText
import smtplib

HOSTNAME = ""
VERSION = ""

DEBUG = False
api = None
SIMULATE = False

ARTIFACTS = None
CACHE_IDS = []

## *************************************** ##

# Update ResultFile UDF
def update_resrev(pinp_dict,flagres,udfname):

    for k,v in pinp_dict.items():

        pinp_XML = api.GET(v) # get artifact

        pinp_DOM = parseString(pinp_XML)

        api.setUDF(pinp_DOM,udfname,flagres)

        # Update Object
        api.PUT(pinp_DOM.toxml(), v)

## *************************************** ##

## Send Notification Email to Operations
def sendmail(samp_nxt_dict):

    body = 'Results Posted Status: \r\n'

    for k,v in samp_nxt_dict.items():
        if v == 0:
            body+= k + ' ' + 'not posted\r\n'
        else:
            body+= k + ' ' + 'successful\r\n'

    # For this example, assume that
    # the message contains only ASCII characters.
    msg = MIMEText(body, 'plain', 'utf-8')

    # me == the sender's email address
    # you == the recipient's email address

    me = 'internal@ixcela.com'
    you = 'internal@ixcela.com'

    msg['Subject'] = 'Customer Results Posting Update'
    msg['From'] = me
    msg['To'] = you

    # Send the message via our own SMTP server, but don't include the
    # envelope header.

    # replace "localhost" below with the IP address of the mail server
    try:
        # s = smtplib.SMTP_SSL('smtp.gmail.com',465)
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.ehlo()
        s.starttls()
        s.login('internal@ixcela.com', 'StarFormatEmail0!')
    except:
        print('Something went wrong')

    s.sendmail(me, you, msg.as_string().encode('ascii'))
    s.close()

## *************************************** ##

## *************************************** ##

def sendMail2(body,to_address,subject):

    # For this example, assume that
    # the message contains only ASCII characters.
    msg = MIMEText(body, 'plain', 'utf-8')

    # me == the sender's email address
    # you == the recipient's email address
    me = 'lab@ixcela.com'
    if len(to_address) == 0:
        you = 'lab@ixcela.com'
    else:
        you = to_address

    msg['Subject'] = subject
    msg['From'] = me
    msg['To'] = you

    # Send the message via our own SMTP server, but don't include the
    # envelope header.

    # replace "localhost" below with the IP address of the mail server
    try:
        # s = smtplib.SMTP_SSL('smtp.gmail.com',465)
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.ehlo()
        s.starttls()
        s.login('lab@ixcela.com', 'ElectroAvenueDetect99!')
    except:
        print('Something went wrong')

    s.sendmail(me, you, msg.as_string().encode('ascii'))
    s.close()

    #print('t')

## *************************************** ##

## Function to set 'next steps' based on the 'Next Step' UDF selected by the LIMS user
def setnxtsteps(samp_nxt_dict):

    stURI = api.getBaseURI() + 'steps/' + args.processLuid + '/actions'
    stXML = api.GET(stURI)
    stDOM = parseString(stXML)

    cnode = stDOM.getElementsByTagName('configuration')
    cnodeuri = cnode[0].getAttribute('uri')

    # Get 'next-action' URI from stepURI
    nxtURI = api.GET(cnodeuri)
    nxtDOM = parseString(nxtURI)
    transtag = nxtDOM.getElementsByTagName('transition')

    if transtag:
        nsURI = transtag[0].getAttribute('next-step-uri')
    else:
        nsURI = ''

    nxtnodes = stDOM.getElementsByTagName('next-action')

    for nnode in nxtnodes:
        ## ignore any nodes that already have an action attribute
        if not nnode.hasAttribute('action'):
            nodeuri = nnode.getAttribute('artifact-uri')

            nXML = api.GET(nodeuri)
            nDOM = parseString(nXML)

            artname = (nDOM.getElementsByTagName('name'))[0].firstChild.data
            artname = str(artname)

            try:
                nxtflag = samp_nxt_dict[artname] # retrieve whether the flag is set to 0 ('Review') or 1 ('Next Step')

                if nxtflag == 1: # set 'next steps' to 'nextstep'
                    artaction = 'nextstep'
                    nnode.setAttribute('action', artaction)

                    if len(nsURI) > 0:
                        nnode.setAttribute('step-uri', nsURI)

                elif nxtflag == 0: # set 'next steps' to review
                    artaction = 'review'
                    nnode.setAttribute('action', artaction)

            except KeyError:
                continue

    ## Update LIMS
    rXML = api.PUT(stDOM.toxml(), stURI)

    stURImod = api.getBaseURI() + 'steps/' + args.processLuid

    try:
        rDOM = parseString(rXML)
        nodes = rDOM.getElementsByTagName('next-action')
        if len(nodes) >= 1:
           pass
        else:
            api.reportScriptStatus(stURImod, "ERROR",
                                       "An error occured while trying to set Next Actions to default value:" + rXML)
    except:
        api.reportScriptStatus(stURImod, "ERROR",
                                   "An error occured while trying to set Next Actions to default value:" + rXML)

    #print('t')

## *************************************** ##

# Hubspot Transactional Emails
def hubspot_trans(tId,cust_email,fname, selplanType, headers):

    pURL = 'https://api.hubapi.com/email/public/v1/singleEmail/send'
    payload = {'emailId': tId, 'message': {'to': cust_email}, "contactProperties": [{"name": "firstname", "value": fname},{"name":"ixcela_program", "value": str(selplanType)}]}

    r = requests.post(pURL, json=payload, headers=headers)

    #print(r.text)

## *************************************** ##

## Function to check 'Next Step' UDF, 'Post' results to MODX, create a supplement file to upload to Makers, and call 'setnxtsteps'
def post2user():

    # For Supplement file
    nowd = date.today()
    ordernum = nowd.strftime('%m%d%y')
    suppfname = args.filename + '_'+ ordernum + '.txt'
    suppfid = open(suppfname,'w')

    suppbottles = {'1': 2, '2': 4, '3': 1, '4': 2, '5': 2, '6': 2, '7': 2, '8': 2}  # serving for each supplement (4 mo supply)
    oid = 1  # Counter for order number field

    # ************************************************************************************************************ #

    ## Get the input and output artifacts to this process
    pURI = api.getBaseURI() + "processes/" + args.processLuid
    pXML = api.GET(pURI)
    pDOM = parseString(pXML)

    inelements = pDOM.getElementsByTagName("input")
    outelements = pDOM.getElementsByTagName("output")

    ## Find the outputs that are 'Per Input' in order to access the 'Next Steps' udf
    outlen = len(outelements)
    perinp_loc = []  # list of locations of outelements that are 'PerInput'
    out_types = [perinp_loc.append(x) for x in range(outlen) if
                 (outelements[x].getAttribute('output-generation-type') == 'PerInput')]

    art_uris = [outelements[y].getAttribute('uri') for y in perinp_loc]

    ## Remove 'state' suffix from artifact uri list
    qmark_loc = [q.index('?') for q in art_uris]  # location of the '?' that precedes the 'state=123' tag
    art_uris2 = [(art_uris[ql][:qmark_loc[ql]]) for ql in range(len(qmark_loc))]  # remove the '?state=123' tag

    # List to handle 'Set Next Steps'
    samp_nxt_dict = dict()
    pinp_dict = dict()

    # **************************************************************************************************** ##

    # New Commercial Sales Subscription Products

    compProLst = ['Ixcela Pro Complete', 'Ixcela Pro Supported', 'Ixcela FX']  # no supplements for 'Ixcela Pro Directed'

    # Subscription Names (over time) for Ixcela Complete

    compNames = ['Ixcela Complete', 'Complete', 'Monthly Subscription', 'Ixcela Unlimited']

    # Single Kit Products - used for the 'Upgrade to Complete' option

    kitNames = ['Ixcela Assess', 'Assess', 'Assess (BP)', 'Prepaid', 'Promo']

    # **************************************************************************************************** ##

    ## Set up parameters for Hubspot Transactional API

    client_id = 'c489b291-6002-4545-a77d-4c85960f09f9'
    client_secret = 'c5058a86-0168-4acb-82e0-c7234200e861'
    redirect_uri = 'https://www.example.com/'

    payload = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': '47119c8f-25cc-452d-9258-e2a527f4c903'
    }

    get_uri = 'https://app.hubspot.com/oauth/authorize?client_id=' + client_id + '&scope=contacts%20automation&redirect_uri=' + redirect_uri

    r1 = requests.post('https://api.hubapi.com/oauth/v1/token', data=payload)
    # print(r.content)

    # Refresh Tokens
    refresh_payload = {
        'grant_type': 'refresh_token',
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': '2bb8fd40-ba90-4cb3-a52e-b73937d5bf4b'
    }

    if r1.reason == 'Bad Request':
        rFresh = requests.post('https://api.hubapi.com/oauth/v1/token', data=refresh_payload)

    responseDict = rFresh.json()

    headers = {'Authorization': 'Bearer ' + str(responseDict['access_token']),
               'Content-Type': 'application/json'}

    # **************************************************************************************************** #

    salesDict = dict()  # dict to store info for customers who have 'source_tag' as 'Sales'

    upgradeDict = dict()  # dict to store info for customers who will be sent the option to 'Upgrade to Complete'

    for auri in art_uris2:

        aXML = api.GET(auri)
        aDOM = parseString(aXML)

        samp_dom = aDOM.getElementsByTagName('name')
        samp_name = str(samp_dom[0].firstChild.data)

        # Create dictionary to be used if POST is not successful to populate 'Reason for Review' ResultFile UDF
        pinp_dict[samp_name] = auri

        ## Check value of 'ResultFile' UDF - 'Next Steps'
        nstepudf = aDOM.getElementsByTagName('udf:field')

        # Currently there is only one 'ResultFile' UDF - 'Next Steps' but this might change in the future

        if str((nstepudf[0].firstChild.data)) == 'Stop':

            # Set 'Next Steps' flag to 'review'
            samp_nxt_dict[samp_name] = 0

            # Set ResultFile UDF 'Reason for Review'
            res4rev = 'User Selected Stop'
            api.setUDF(aDOM,'Reason for Review', res4rev)

            # Update Object
            msgput = api.PUT(aDOM.toxml(), auri)

            ## Update 'Review Reason' Sample UDF
            # Get sample uri
            sampnode = aDOM.getElementsByTagName('sample')
            samp = sampnode[0].getAttribute('uri')

            sXML = api.GET(samp)
            sDOM = parseString(sXML)

            revreasons = str(api.getUDF(sDOM, 'ReviewReason'))

            if revreasons != '':  # if UDF is not empty
                revreasons = revreasons + ', User Selected Stop'
            else:
                revreasons = 'User Selected Stop'

            api.setUDF(sDOM, 'ReviewReason', revreasons)

            # Update Object
            api.PUT(sDOM.toxml(), samp)

        else:

            dataPost = list() # List to contain the dictionary of results for this user

            sampnode = aDOM.getElementsByTagName('sample')
            samp = sampnode[0].getAttribute('uri')

            # ******************************************************************* #

            ## Retrieve the 'HTI_text' UDF - this has the entire Result Report for each user

            ## Get sample uri
            sXML = api.GET(samp)
            sDOM = parseString(sXML)

            namedomlst = sDOM.getElementsByTagName('name')
            sname = namedomlst[0].firstChild.data

            # Retrieve UDF's

            reportTxt = api.getUDF(sDOM,'HTI_text') # Contains the entire JSON for each customer
            reportDict = json.loads(reportTxt)

            dataPost.append(reportDict) # Append to the list that will get POSTed

            currfname = str(api.getUDF(sDOM, 'First Name'))
            curremail = str(api.getUDF(sDOM, 'Email'))
            plantype = str(api.getUDF(sDOM, 'Plan Type'))  # Only plans in 'compNames' and 'compProLst' get supplements
            currlname = str(api.getUDF(sDOM, 'Last Name'))
            overallscore = int(str(api.getUDF(sDOM, 'Overall Score')))
            currwebID = int(str(api.getUDF(sDOM, 'Web Customer ID')))

            # ******************************************************************* #

            ## POST to MODX - individually and if successful send Hubspot Transactional Email
            allData = dict()
            allData['data'] = dataPost

            urlModx = 'http://dev2.ixcela.modxcloud.com/api/v1/save-results.json'
            headersModx = {'Authorization': 'Bearer 08e7d34d3c82456b5d72563a979115cc3ce97ddd',
                           'Content-Type': 'application/json'}

            rModx = requests.post(urlModx, data=json.dumps(allData), headers=headersModx)

            if rModx.status_code != requests.codes.ok:  # did not POST successfully
                samp_nxt_dict[samp_name] = 0  # set flag to 'review'

                # Update ResultFile UDF 'Reason for Review'
                udfname = 'Reason for Review'
                update_resrev(pinp_dict, 'POST to MODX Failed', udfname)

            else:

                # ******************************************************************* #

                # Set 'Next Steps' flag to 'nextstep' and append to data structure that gets Posted to MODX
                # Update 'ResultCompleted' Sample UDF

                # Update sample UDF 'ResultCompleted' to have a value = 1 - indicates results completed and posted

                resComp = api.getUDF(sDOM,'ResultCompleted')
                resComp = 1
                api.setUDF(sDOM, 'ResultCompleted', resComp)

                # Sales Related Info
                pCode = str(api.getUDF(sDOM,'promo_code'))
                sCode = str(api.getUDF(sDOM,'source_tag'))

                if sCode == 'Sales':

                    salesDict[samp_name] = [currfname,currlname]

                # Update Object

                api.PUT(sDOM.toxml(), samp)

                samp_nxt_dict[samp_name] = 1

                if plantype == 'Prepaid':
                    selplanType = 'Promo'
                else:
                    selplanType = plantype

                bpVal = len(reportDict['attributes']['simpleSteps']['bodyWeekTablePartner'])

                if bpVal > 0:

                    selplanType = 'Assess (BP)'

                # ******************************************************************* #

                # POST to MODX successful
                # Send Hubspot Email

                hubspot_trans(7596572684,curremail,currfname,selplanType, headers)

                # ******************************************************************* #

                # Append customer to list to 'Upgrade to Complete' if selplanType is in kitNames

                if selplanType in kitNames:
                    upgradeDict[samp_name] = currwebID

                # ******************************************************************* #

                # Supplements

                if (selplanType in compProLst) or (selplanType in compNames):

                    currsuppTxt = api.getUDF(sDOM, 'SuppList')
                    currsupp = json.loads(currsuppTxt)
                    # currsupp = currsupp.split(',') # Generate list of supplements
                    currsupp = [str(xsp) for xsp in currsupp]

                    curradd = api.getUDF(sDOM, 'Address')
                    curradd = curradd.split('<abr>')  # Generate list of address (street, city, state, zip, country)
                    curradd = [str(xad) for xad in curradd]

                    currfullname = currfname + ' ' + currlname
                    temporder = ordernum + str(oid)
                    oid = oid + 1

                    if (len(currsupp) == 1) and (currsupp[0] is ''):  # if there are no suggestions

                        try:

                            # add 'Biome Support' to supplement recommendation

                            numbot = str(suppbottles['3'])
                            rowinf = [temporder, '', 'USPS', 'Priority Mail Flat Rate Envelope', 'Prepaid', '', '', '', '',
                                      curradd[0], currfullname, curradd[1], curradd[2], curradd[3], curradd[4], curradd[5],
                                      curradd[6], '', '', curremail, '', '', '', '3', numbot]

                            suppfid.write('\t'.join(rowinf) + '\n')

                        except IndexError:
                            print('Potential Error in Address for WebID: ', currwebID)

                    else:

                        try:

                            for csupp in currsupp:
                                numbot = str(suppbottles[csupp])
                                rowinf = [temporder, '', 'USPS', 'Priority Mail Flat Rate Envelope', 'Prepaid', '', '', '',
                                          '', curradd[0], currfullname, curradd[1], curradd[2], curradd[3], curradd[4],
                                          curradd[5], curradd[6], '', '', curremail, '', '', '', csupp, numbot]

                                suppfid.write('\t'.join(rowinf) + '\n')

                        except IndexError:
                            print('Potential Error in Address for WebID: ', currwebID)

    # close 'Supplement File'

    suppfid.close()

    # ******************************************************************* #

    # Set Next Steps

    setnxtsteps(samp_nxt_dict)

    # ******************************************************************* #

    # Email Operations
    sendmail(samp_nxt_dict)

    # ******************************************************************* #

    # Email Sales

    if len(salesDict) > 0:

        salesYes = 'TEST: Results for following sales kits have been posted to the customer account: \r\n'

        sY = 0

        for k, v in salesDict.items():
            salesYes = salesYes + ' - ' + v[0] + ' ' + v[1] + '\r\n'

        sendMail2(salesYes, 'salesteam@ixcela.com', 'Sales Kits Results Posted')

    # ******************************************************************* #

    # Upgrade to Complete

    if upgradeDict:

        postLst = list()

        for k, v in upgradeDict.items():

            tempdict = dict()

            tempdict['user'] = v

            postLst.append(tempdict)

        postLoad = dict()

        postLoad['data'] = postLst

        # Post to MODX

        upgUrl = 'http://dev2.ixcela.modxcloud.com/api/v1/start-trial.json'

        headersModx = {'Authorization': 'Bearer 9d64cbdf3ff66791f3dd335f46e3c4d2a85899e8',
                       'Content-Type': 'application/json'}

        rModx = requests.post(upgUrl, data=json.dumps(postLoad), headers=headersModx)

        if rModx.status_code != requests.codes.ok:  # did not POST successfully

            print('Upgrade to Complete POST not Successful')

        else:

            print('Upgrade to Complete POST Successful')

    # ******************************************************************* #

## ******************************************************************* ##

def setupArguments():
    Parser = OptionParser()
    Parser.add_option('-l', "--processLuid", action='store', dest='processLuid')
    Parser.add_option('-u', "--username", action='store', dest='username')
    Parser.add_option('-p', "--password", action='store', dest='password')
    Parser.add_option('-s', "--stepURI", action='store', dest='stepURI')
    Parser.add_option('-f', "--filename", action='store', dest='filename')

    return Parser.parse_args()[0]

def main():

    global api
    global args

    #args = {}
    args = setupArguments()

    '''
    args[ "processLuid" ]= "24-2680"
    args[ "username" ] = "ssarangi"
    args[ "password" ] = "Ixcela16!"
    args['stepURI'] = "https://ixcela-test.claritylims.com/api/v2/configuration/protocols/53/steps/104"
    args['filename'] = 'suppfile.txt'
    '''

    api = glsapiutil.glsapiutil2()
    #api.setURI(args['stepURI'])
    #api.setup(args['username'], args['password'])
    api.setURI(args.stepURI)
    api.setup( args.username, args.password)

    ## at this point, we have the parameters the EPP plugin passed, and we have network plumbing
    ## so let's get this show on the road!
    post2user()

if __name__ == "__main__":
    main()