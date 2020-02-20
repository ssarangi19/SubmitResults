import json
import requests

usrUrl = 'http://dev2.ixcela.modxcloud.com/api/v1/users.json'
headersModx = {'Authorization': 'Bearer 88b2e69b60e1bef159245fb679ec33ac7b6cb0a3',
               'Content-Type': 'application/json'}

tempDict = dict()
tempDict['data'] = dict()

tempDict['data']['user'] = int('324')

rMODX = requests.post(usrUrl, data=json.dumps(tempDict), headers=headersModx)

usrData = rMODX.json()['data'][0]

modx_usr = usrData['meta']

temp_name = str((usrData['attributes']['fullname']).encode('ascii', 'ignore'))

shipFname = ''
shipLname = ''


print(rMODX.content)
