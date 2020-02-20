## The purpose of this script is to post results to a customer's account on MODX
## The script also sends a notification email to the customer that their results are ready

## The script also generates a supplement file for the customers on the Ixcela Complete program to be uploaded to
## the Makers portal - THIS SHOULD BE CHANGED TO USING THE MAKERS API

## The decision to post results to a customer's account is based on the value of the ResultFile UDF 'Next Steps', which
## can either be 'Proceed' or 'Stop'

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

# Update ResultFile UDF
def update_resrev(pinp_dict,flagres,udfname):

    for k,v in pinp_dict.items():

        pinp_XML = api.GET(v) # get artifact

        pinp_DOM = parseString(pinp_XML)

        api.setUDF(pinp_DOM,udfname,flagres)

        # Update Object
        api.PUT(pinp_DOM.toxml(), v)


## Send Notification Email
def sendmail(first_name, to_address):

    body = 'Dear ' + first_name + ', \r\n' + '\r\nYour results are now available to view on your Ixcela account. Please follow the instructions below to access your results:\r\n'\
              + '\r\ni) Go to www.ixcela.com/member/login\r\n' \
              + '\r\nii) Click on the \'View Test Results\' button under your account information or on the \'My Test Results\' tab\r\n' \
              + '\r\niii) To save the report - click the printer icon on the top right and select the destination as \'Save As PDF\'. Hit \'Save\'\r\n' \
              + '\r\nIf you had signed up for the Ixcela Complete program, your supplements will be shipped out in the next couple of days.\r\n'\
              + '\r\nPlease email us at support@ixcela.com if you have any questions or feedback.\r\n' + '\r\nThank you!\r\n'\
              + '\r\nIxcela Support Team\r\n'

    # For this example, assume that
    # the message contains only ASCII characters.
    msg = MIMEText(body, 'plain', 'utf-8')

    # me == the sender's email address
    # you == the recipient's email address
    me = 'support@ixcela.com'
    if len(to_address) == 0:
        you = 'support@ixcela.com'
    else:
        you = to_address

    msg['Subject'] = 'Your Ixcela Test Results'
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
        s.login('support@ixcela.com', '135SouthRd')
    except:
        print('Something went wrong')

    s.sendmail(me, you, msg.as_string().encode('ascii'))
    s.close()


## Function to set 'next steps' based on the 'Next Step' UDF selected by the LIMS user
def setnxtsteps(samp_nxt_dict):

    stURI = api.getBaseURI() + 'steps/' + args['processLuid'] + '/actions'
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
                    if samp_nxt_dict['all'] == 0:
                        artaction = 'review'
                        nnode.setAttribute('action', artaction)
                    else:
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

    stURImod = api.getBaseURI() + 'steps/' + args['processLuid']

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


## Function to check 'Next Step' UDF, 'Post' results to MODX, create a supplement file to upload to Makers, and call 'setnxtsteps'
def post2user():

    ## Declarations

    # For JSON file output
    allsamp_data = []  # list that contains all samples in form of dictionaries
    dict_allsamp = dict()  # dictionary that contains a list of dictionaries

    # category names for json output
    catnamesdict = {'gastrointestinal':'GI Score', 'immuno':'IF Score', 'emotional':'EB Score', 'cognitive':'CA Score', 'energetic':'EE Score'}

    # metnames dict
    metdict = {'methylxanthine':'3MX','hydroxybenzoic':'4HBAC','acetic':'IAA','lactic':'ILA','propionic':'IPA','indoxyl':'IDS','kynurenine':'KYN','serotonin':'SER','tryptophan':'TRP','tyrosine':'TYR','uricAcid':'UA','xanthine':'XAN'}

    # For Supplement file
    now = date.today()
    ordernum = str(now.month) + str(now.day) + (str(now.year))[2:]
    suppfname = ordernum +'_' + args['filename']
    suppfid = open(suppfname,'w')

    suppbottles = {'1':2, '2':4, '3':4, '4':2, '5':2, '6':2, '7':2, '8':2} # serving for each supplement (4 mo supply)
    oid = 1  # Counter for order number field

    ## ******************************************************************* ##

    ## Get the input and output artifacts to this process
    pURI = api.getBaseURI() + "processes/" + args["processLuid"]
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

            # Set 'Next Steps' flag to 'nextstep' and append to data structure that gets Posted to MODX
            samp_nxt_dict[samp_name] = 1

            sampnode = aDOM.getElementsByTagName('sample')
            samp = sampnode[0].getAttribute('uri')


            '''      
            inp_uris = [x.getAttribute('uri') for x in inelements]

            ## Find unique input artifact uri's
            uniq_inps = []
            templst = [uniq_inps.append(x) for x in inp_uris if x not in uniq_inps]

            ## Remove 'state' suffix from artifact uri list
            qmark_loc = [q.index('?') for q in uniq_inps]  # location of the '?' that precedes the 'state=123' tag
            uniq_inps2 = [(uniq_inps[ql][:qmark_loc[ql]]) for ql in range(len(qmark_loc))]  # remove the '?state=123' tag

            ## Get sample name
            iXML = api.getArtifacts(uniq_inps2)
            iDOM = parseString(iXML)

            sampdomlst = iDOM.getElementsByTagName('sample')
            sampuris = [x.getAttribute('uri') for x in sampdomlst]  # extract sample uris
            '''
            ## ******************************************************************* ##

            ## Retrieve the sample-specific information that will be posted
            ## Relevant Sample UDF's include: Metabolite Concentrations; Category and Overall Scores; 'How to Improve' Text; Supplement list
            ## Web Customer ID; Sample Collection Date; Sample Received Date; Plan Type

            #for samp in sampuris:

            # json file output declarations
            lst_dict_met = []  # list for all metabolite names and concentrations
            lst_dict_cat = []  # list for all category scores and 'How To Improve' text for this sample

            ## Get sample uri
            sXML = api.GET(samp)
            sDOM = parseString(sXML)

            namedomlst = sDOM.getElementsByTagName('name')
            sname = namedomlst[0].firstChild.data

            # Retrieve UDF's

            # 'How to Improve' text
            gentext_all = api.getUDF(sDOM,'HTI_text')
            gentext = gentext_all.split('<cbreak>') # split 'How to Improve' text into the 5 categories

            # Scores

            jc = 0 # counter for text recommendations

            for k2,v2 in catnamesdict.items():

                dict_cat = dict()
                dict_cat['name'] = k2
                dict_cat['value'] = api.getUDF(sDOM,v2)
                dict_cat['text'] = '<p>' + gentext[jc] + '</p>'

                # List of metabolite concentrations
                lst_dict_cat.append(dict_cat)  # add dict to list for category scores and 'How To Improve' text

                jc = jc + 1 # increase counter

            overallscore = api.getUDF(sDOM,'Overall Score')

            # Metabolite Conc's

            for k,v in metdict.items():

                # metabolites dictionary for json file output
                dict_met = dict()
                dict_met['name'] = k
                dict_met['value'] = api.getUDF(sDOM,v) # retrieve appropriate metabolite value

                # List of metabolite concentrations
                lst_dict_met.append(dict_met)  # add dict to list for metabolite names and concentrations

            # Dictionary of 'attributes'
            dict_attr = dict()

            sampcolldate = str(api.getUDF(sDOM,'SampleCollectionDate'))
            samprecdate = str(api.getUDF(sDOM,'SampleReceivedDate'))

            dict_attr['dateTaken'] = (datetime.strptime(sampcolldate, '%Y-%m-%d')).strftime('%B %d, %Y')
            dict_attr['dateReceived'] = (datetime.strptime(samprecdate, '%Y-%m-%d')).strftime('%B %d, %Y')
            dict_attr['score_overall'] = overallscore  # 'Overall Score' across the 5 categories for this sample
            dict_attr['scores'] = lst_dict_cat  # Scores and 'How To Improve' text for all categories
            dict_attr['metabolites'] = lst_dict_met  # Metabolite concentrations and names

            # Sub-dictionary of 'data'
            dict_subdat = dict()
            dict_subdat['type'] = 'modUser'
            dict_subdat['id'] = api.getUDF(sDOM,'Web Customer ID')  # 'WebID' field in metabolite_values.csv file

            # Dictionary of 'data'
            dict_data = dict()
            dict_data['data'] = dict_subdat

            # Sub-dictionary of 'user'
            dict_user = dict()
            dict_user['user'] = dict_data  # 'User' value is 'dict_subdat'

            # Root Dictionary per sample
            dict_sample = dict()
            dict_sample['type'] = 'TestKitResult'
            dict_sample['id'] = sname # Kit ID/ Sample Name
            dict_sample['relationships'] = dict_user
            dict_sample['attributes'] = dict_attr

            # Add to the list that will get posted to MODX
            allsamp_data.append(dict_sample)

            # Update sample UDF 'ResultCompleted' to have a value = 1 - indicates results completed and posted
            api.setUDF(sDOM,'ResultCompleted', 1)

            # Update Object
            api.PUT(sDOM.toxml(),samp)

            # Retrieve email and first name of customer
            curremail = str(api.getUDF(sDOM, 'Email'))
            currfname = str(api.getUDF(sDOM, 'First Name'))

            # Send Notification Email to customer
            sendmail(currfname,curremail)

            ## ******************************************************************* ##

            ## Supplements
            plantype = str(api.getUDF(sDOM,'Plan Type')) # Only 'Complete' plans get supplements

            if plantype == 'Complete':
                currsupp = api.getUDF(sDOM,'SuppList')
                currsupp = currsupp.split(',') # Generate list of supplements
                currsupp = [str(xsp) for xsp in currsupp]

                curradd = api.getUDF(sDOM,'Address')
                curradd = curradd.split('<abr>') # Generate list of address (street, city, state, zip, country)
                curradd = [str(xad) for xad in curradd]

                currlname = api.getUDF(sDOM,'Last Name')
                currfullname = currfname + ' ' + str(currlname)
                temporder = ordernum + str(oid)
                oid = oid + 1

                if (len(currsupp)==1) and (currsupp[0] is ''): # if there are no suggestions

                    # add 'Biome Support' to supplement recommendation (always gets recommended)
                    numbot = str(suppbottles['3'])
                    rowinf = [temporder, '', 'USPS', 'Priority Mail Flat Rate Envelope', 'Prepaid', '', '', '', '', '',
                              currfullname, curradd[0], curradd[1], curradd[2], curradd[3], curradd[4], curradd[5], '',
                              '', curremail, '', '', '', '3', numbot]

                    suppfid.write('\t'.join(rowinf) + '\n')

                else:

                    if '3' not in currsupp: # if 'Biome Support' is not in the list of recommendations
                        numbot = str(suppbottles['3'])
                        rowinf = [temporder, '', 'USPS', 'Priority Mail Flat Rate Envelope', 'Prepaid', '', '', '', '',
                                  '',
                                  currfullname, curradd[0], curradd[1], curradd[2], curradd[3], curradd[4], curradd[5],
                                  '',
                                  '', curremail, '', '', '', '3', numbot]

                        suppfid.write('\t'.join(rowinf) + '\n')

                    else:

                        for csupp in currsupp:
                            numbot = str(suppbottles[csupp])
                            rowinf = [temporder,'','USPS','Priority Mail Flat Rate Envelope','Prepaid','','','','','', currfullname, curradd[0],curradd[1],curradd[2],curradd[3],curradd[4],curradd[5],'','',curremail,'','','',csupp,numbot]

                            suppfid.write('\t'.join(rowinf) + '\n')

    # close 'Supplement File'
    suppfid.close()

    ## ******************************************************************* ##

    ## Post Results

    # create JSON file to upload to MODX
    dict_allsamp['data'] = allsamp_data

    # Upload to MODX

    # url = 'https://ixcela.com/api/v1/save-results.json'
    # headers = {'Authorization':'Bearer 350deaa48daf12e5d3373b8644481217fc8acb5e','Content-Type':'application/json'}

    url = 'http://dev2.ixcela.modxcloud.com/api/v1/save-results.json'
    headers = {'Authorization':'Bearer 9b5228db042005d06e68285eb5a008ed2103fc0a','Content-Type':'application/json'}

    r = requests.post(url,data=json.dumps(dict_allsamp),headers=headers)

    if r.status_code != requests.codes.ok: # did not POST successfully
        samp_nxt_dict['all'] = 0 # set flag to 'review' for a key == 'all' corresponding to all samples

        # Update ResultFile UDF 'Reason for Review'
        udfname = 'Reason for Review'
        update_resrev(pinp_dict,'POST to MODX Failed', udfname)

    else:
        samp_nxt_dict['all'] = 1 # set flag to 'nextstep' if POST is successful

    ## ******************************************************************* ##

    ## Set Next Steps

    setnxtsteps(samp_nxt_dict)

    #print('t')


def setupArguments():
    Parser = OptionParser()
    Parser.add_option('-l', "--processLuid", action='store', dest='processLuid')
    Parser.add_option('-u', "--username", action='store', dest='username')
    Parser.add_option('-p', "--password", action='store', dest='password')
    Parser.add_option('-s', "--stepURI", action='store', dest='stepURI')
    Parser.add_option('-f', "--filename", action='store', dest="filename")

    return Parser.parse_args()[0]

def main():

    global api
    global args

    args = {}
    #args = setupArguments()

    args[ "processLuid" ]= "24-1851"
    args[ "username" ] = "ssarangi"
    args[ "password" ] = "Ixcela16!"
    args['stepURI'] = "https://ixcela-test.claritylims.com/api/v2/configuration/protocols/53/steps/104"
    args['filename'] = 'suppfile.txt'

    # setupGlobalsFromURI( args[ "stepURI" ] )
    api = glsapiutil.glsapiutil2()
    api.setURI(args['stepURI'])
    api.setup(args['username'], args['password'])
    #api.setURI(args.stepURI)
    #api.setup( args.username, args.password)

    ## at this point, we have the parameters the EPP plugin passed, and we have network plumbing
    ## so let's get this show on the road!
    post2user()

if __name__ == "__main__":
    main()