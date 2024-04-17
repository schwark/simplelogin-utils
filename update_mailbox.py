from simplelogin import SimpleLogin
import logging
import argparse

logging.basicConfig(level=logging.INFO)
parser = argparse.ArgumentParser(description='Utility to bulk update aliases from one mailbox to another')
parser.add_argument('-k', '--key',
                    help='SimpleLogin api key')
parser.add_argument('-s', '--src',
                    help='the mailbox email address to change from')
parser.add_argument('-d', '--dest',
                    help='the mailbox email address to change to')
args = parser.parse_args()

if not args.key:
    logging.fatal('API Key missing')
    exit()
client = SimpleLogin(apikey=args.key)
m = client.get_mailboxes()
for mailbox in m:
    if args.src and args.src in mailbox['email']:
        src_id = mailbox['id']
        logging.info('found source mailbox id: '+str(src_id)) 
    if args.dest and args.dest in mailbox['email']: 
        dest_id = mailbox['id']
        logging.info('found dest mailbox id: '+str(dest_id))
if not src_id:
    logging.fatal('Could not find mailbox for '+args.src)
    exit()
if not dest_id:
    logging.fatal('Could not find mailbox for '+args.dest)
    exit()
a = client.get_aliases()
for alias in a:
    boxes = [x['id'] for x in alias['mailboxes']]
    if src_id not in boxes: continue
    upd_boxes = [dest_id if x == src_id else x for x in boxes]
    print(alias['email'], alias['mailbox']['email'])
    result = client.alias_mailbox(alias['id'], upd_boxes)
    if result and 'ok' in result and result['ok']:
        logging.info(alias['email']+' updated to '+args.dest)
    else:
        logging.error(alias['email']+' failed to update to '+args.dest)