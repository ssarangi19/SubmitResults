
fid = open('testfile.txt','w')
rowinf = ['212181', '', 'USPS', 'Priority Mail Flat Rate Envelope', 'Prepaid', '', '', '', '', '', 'srikant sarangi',
          '135 South Road', '', 'Bedford', 'MA', '01730', 'USA', '', '', 'srikant@ixcela.com', '', '', '', '2', '4']

fid.write('\t'.join(rowinf) + '\n')