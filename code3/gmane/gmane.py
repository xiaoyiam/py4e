import sqlite3
import time
import ssl
import urllib.request, urllib.parse, urllib.error
from urllib.parse import urljoin
from urllib.parse import urlparse
import re
from datetime import datetime, timedelta

# Deal with SSL certificate anomalies Python > 2.7
# scontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
scontext = None

# Not all systems have this so conditionally define parser
try:
    import dateutil.parser as parser
except:
    pass

def parsemaildate(md) :
    # See if we have dateutil
    try:
        pdate = parser.parse(tdate)
        test_at = pdate.isoformat()
        return test_at
    except:
        pass

    # Non-dateutil version - we try our best

    pieces = md.split()
    notz = " ".join(pieces[:4]).strip()

    # Try a bunch of format variations - strptime() is *lame*
    dnotz = None
    for form in [ '%d %b %Y %H:%M:%S', '%d %b %Y %H:%M:%S',
        '%d %b %Y %H:%M', '%d %b %Y %H:%M', '%d %b %y %H:%M:%S',
        '%d %b %y %H:%M:%S', '%d %b %y %H:%M', '%d %b %y %H:%M' ] :
        try:
            dnotz = datetime.strptime(notz, form)
            break
        except:
            continue

    if dnotz is None :
        # print 'Bad Date:',md
        return None

    iso = dnotz.isoformat()

    tz = "+0000"
    try:
        tz = pieces[4]
        ival = int(tz) # Only want numeric timezone values
        if tz == '-0000' : tz = '+0000'
        tzh = tz[:3]
        tzm = tz[3:]
        tz = tzh+":"+tzm
    except:
        pass

    return iso+tz

conn = sqlite3.connect('content.sqlite')
cur = conn.cursor()
conn.text_factory = str

baseurl = "http://gmane.dr-chuck.net/gmane.comp.cms.sakai.devel/"

cur.execute('''CREATE TABLE IF NOT EXISTS Messages 
    (id INTEGER UNIQUE, email TEXT, sent_at TEXT, 
     subject TEXT, headers TEXT, body TEXT)''')

# This will be manually filled in
cur.execute('''CREATE TABLE IF NOT EXISTS Mapping 
    (old TEXT, new TEXT)''')

# This will be manually filled in
cur.execute('''CREATE TABLE IF NOT EXISTS DNSMapping 
    (old TEXT, new TEXT)''')

start = 0
many = 0
while True:
    if ( many < 1 ) :
        sval = input('How many messages:')
        if ( len(sval) < 1 ) : break
        many = int(sval)

    start = start + 1
    cur.execute('SELECT id FROM Messages WHERE id=?', (start,) )
    try:
        row = cur.fetchone()
        if row is not None : continue
    except:
        row = None
        
    many = many - 1
    url = baseurl + str(start) + '/' + str(start + 1)

    try:
        document = urllib.request.urlopen(url, context=scontext)
        text = document.read()
        if document.getcode() != 200 :
            print("Error code=",document.getcode(), url)
            break
    except KeyboardInterrupt:
        print('')
        print('Program interrupted by user...')
        break
    except:
        print("Unable to retrieve or parse page",url)
        break

    print(url,len(text))

    if not text.startswith("From "):
        print(text)
        print("End of mail stream reached...")
        quit ()

    pos = text.find("\n\n")
    if pos > 0 : 
        hdr = text[:pos]
        body = text[pos+2:]
    else:
        print(text)
        print("Could not find break between headers and body")
        break

    email = None
    x = re.findall('\nFrom: .* <(\S+@\S+)>\n', hdr)
    if len(x) == 1 : 
        email = x[0];
        email = email.strip().lower()
        email = email.replace("<","")
    else:
        x = re.findall('\nFrom: (\S+@\S+)\n', hdr)
        if len(x) == 1 : 
            email = x[0];
            email = email.strip().lower()
            email = email.replace("<","")

    date = None
    y = re.findall('\Date: .*, (.*)\n', hdr)
    if len(y) == 1 : 
        tdate = y[0]
        tdate = tdate[:26]
        try:
            sent_at = parsemaildate(tdate)
        except:
            print(text)
            print("Parse fail",tdate)
            break

    subject = None
    z = re.findall('\Subject: (.*)\n', hdr)
    if len(z) == 1 : subject = z[0].strip().lower();

    print("   ",email,sent_at,subject)
    cur.execute('''INSERT OR IGNORE INTO Messages (id, email, sent_at, subject, headers, body) 
        VALUES ( ?, ?, ?, ?, ?, ? )''', ( start, email, sent_at, subject, hdr, body))
    conn.commit()
    time.sleep(1)

cur.close()

