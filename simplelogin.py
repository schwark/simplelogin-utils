import sys
import logging
from http.cookies import SimpleCookie
import requests
import json
import ssl

MAX_RESULTS = 20

ssl._create_default_https_context = ssl._create_unverified_context
log = logging.getLogger('pysimplelogin')

class SimpleLogin(object):

    def __init__(self, apikey=None):
        self.base = 'https://api.simplelogin.io'
        self.apikey = apikey
        self.session = False
        self.cookies = {}
        self.metadata = self._meta

    _meta = {
        'common': {
            'mailboxes': {
                'result': 'mailboxes',
                'url': '/api/v2/mailboxes'
            },
            'domains': {
                'result': 'suffixes',
                'url': '/api/v5/alias/options'
            },
            'aliases': {
                'paged': True,
                'result': 'aliases',
                'url': lambda sf, **kwargs: '/api/v2/aliases?page_id='+str((kwargs['page'] if 'page' in kwargs else '0'))
            },
            'random': {
                'method': 'POST',
                'url': '/api/alias/random/new'
            },
            'custom': {
                'method': 'POST',
                'url': '/api/v3/alias/custom/new'
            },
            'alias-delete': {
                'method': 'DELETE',
                'url': lambda sf, **kwargs: '/api/aliases/'+str(kwargs['id'] if 'id' in kwargs else '')
            },
            'alias-toggle': {
                'method': 'POST',
                'url': lambda sf, **kwargs: '/api/aliases/'+str(kwargs['id'] if 'id' in kwargs else '')+'/toggle',
            },
            'alias-details': {
                'url': lambda sf, **kwargs: '/api/aliases/'+str(kwargs['id'] if 'id' in kwargs else '')
            },
            'alias-activities': {
                'paged': True,
                'url': lambda sf, **kwargs: '/api/aliases/'+str(kwargs['id'] if 'id' in kwargs else '')+'/activities'
            },
            'alias-contacts': {
                'paged': True,
                'result': 'contacts',
                'url': lambda sf, **kwargs: '/api/aliases/'+str(kwargs['id'] if 'id' in kwargs else '')+'/contacts?page_id='+str((kwargs['page'] if 'page' in kwargs else '0'))
            },
            'alias-contact-new': {
                'method': 'POST',
                'url': lambda sf, **kwargs: '/api/aliases/'+str(kwargs['id'] if 'id' in kwargs else '')+'/contacts',
                'data': {
                    'contact': lambda sf, **kwargs: kwargs['contact']
                }
            },
            'alias-mailbox': {
                'method': 'PUT',
                'url': lambda sf, **kwargs: '/api/aliases/'+str(kwargs['id'] if 'id' in kwargs else '')+'',
                'data': {
                    'mailbox_ids': lambda sf, **kwargs: kwargs['mailbox_id']
                }
            },
            'contact-delete': {
                'method': 'DELETE',
                'url': lambda sf, **kwargs: '/api/contacts/'+str(kwargs['id'] if 'id' in kwargs else '')
            },
            'contact-toggle': {
                'method': 'POST',
                'url': lambda sf, **kwargs: '/api/contacts/'+str(kwargs['id'] if 'id' in kwargs else '')+'/toggle',
            },
        },
    }

    def _get_step_url(self, step, **kwargs):
        result = None
        step_metadata = self._get_step_metadata(step)
        if step_metadata and 'url' in step_metadata:
            url = step_metadata['url'](self, **kwargs) if callable(step_metadata['url']) else step_metadata['url']
            log.debug('using url : '+url)
            result = self.base+url
        return result

    def _get_step_metadata(self, step):
        result = {}
        if step in self.metadata:
            result = self.metadata[step] 
        if step in self._meta['common']:
            result.update(self._meta['common'][step])
        return result

    def _make_request(self, step, **kwargs):
        request_metadata = self._get_step_metadata(step)
        log.debug('kwargs are : '+str(kwargs))
        data = None
        if not request_metadata:
            return None
        if 'data' in request_metadata:
            data = request_metadata['data']
        if 'method' in request_metadata:
            method = request_metadata['method']
        else:
            method = 'GET' if not data else 'POST'
        if 'redirect' in request_metadata:
            redirect = request_metadata['redirect']
        else:
            redirect = True
        headers = {'Host': 'api.simplelogin.io'}
        if self.apikey:
            headers['Authentication'] = self.apikey
            log.debug('setting api key to '+self.apikey)
        request_params = {'url': self._get_step_url(step, **kwargs), 'method': method, 'allow_redirects': redirect, 'headers': headers}
        if(data):
            if isinstance(data, dict):
                data = {k : v(self, **kwargs) if callable(v) else v for k, v in data.items()}
                log.debug(method+'ing data : '+str(data))
                request_params['data'] = json.dumps(data)
                headers['Content-Type'] = 'application/json'
            else:
                request_params['data'] = data
        log.debug("request is "+str(request_params))
        r = requests.request(**request_params)
        if(r.status_code >= 200 and r.status_code <= 400 and 'set-cookie' in r.headers):
            cookies = SimpleCookie()
            cookies.load(r.headers['Set-Cookie'])
            for key, value in cookies.items():
                self.cookies[key] = value.value
        return r

    def _get_results(self, step, **kwargs):
        results = []
        step_metadata = self._get_step_metadata(step)
        # keep trying pages if paged request
        page = 0
        while -1 != page:
            tries = 0 # try a couple of times to resolve stale sessions as necessary
            if 'paged' in step_metadata and step_metadata['paged']:
                kwargs['page'] = page
                log.debug('getting '+step+' page #'+str(page))
                page = page + 1
            while tries < 2:
                log.debug("getting results for "+str(step)+" with args %s", str(kwargs))
                r = self._make_request(step, **kwargs)
                error = self._check_response(r,  step)
                if(not error):
                    tries = 2
                    value = None
                    json = r.json()
                    if json:
                        if 'result' in step_metadata and step_metadata['result'] in json:
                            value = json[step_metadata['result']]
                        else:
                            value = json
                        if 'paged' in step_metadata and step_metadata['paged']:
                            if len(value) < 20:
                                page = -1
                            results.extend(value)
                        else:
                            results = value
                            page = -1
                else:
                    tries += 1
                    log.debug('error '+str(error))
                    results = error
        return results

    def _set_action(self, step, **kwargs):
        result = False
        tries = 0 # try a couple of times to resolve stale sessions as necessary
        while tries < 2:
            r = self._make_request(step, **kwargs)
            result = self._check_response(r,  step)
            if(not result):
                result = True
                tries = 2
            else:
                result = False
                tries += 1
        return result

    def _check_response(self, r, operation):
        result = ''
        request_metadata = self._get_step_metadata(operation)
        if (r.status_code >= 200 and r.status_code <= 400):
            response = r.json() if 'ignore_response' not in request_metadata or not request_metadata['ignore_response'] else None
            if response and 'error' in response:
                log.debug(operation+': failed request with error '+response['error'])
                result = response['error']
        else:
            result = 'http.error.'+str(r.status_code)
            if 401 == r.status_code or 403 == r.status_code:
                self.session = False
            log.debug('API error code : '+result)
        return result
    
    def get_results(self, step, **kwargs):
        return self._get_results(step, **kwargs)

    def get_aliases(self):
        return self._get_results('aliases')

    def get_domains(self):
        domains = self._get_results('domains')
        if domains:
            domains = list(filter(lambda x: x['is_custom'], domains))
        return domains

    def get_mailboxes(self):
        return self._get_results('mailboxes')

    def get_contacts(self, aliases=[]):
        result = []
        for alias in aliases:
            contacts = list(map(lambda x: x.update({'alias': alias['email']}) or x, self._get_results('alias-contacts', id=alias['id'])))
            result.extend(contacts)
        return result
    
    def get_alias(self, id):
        return self._get_results('alias-details', id=id)
    
    def alias_toggle(self, id):
        return self._get_results('alias-toggle', id=id)
        
    def alias_contact_new(self, id, contact):
        return self._get_results('alias-contact-new', id=id, contact=contact)
        
    def alias_mailbox(self, id, mailbox_id):
        if type(mailbox_id) is not list: mailbox_id = [mailbox_id]
        return self._get_results('alias-mailbox', id=id, mailbox_id=mailbox_id)
        
    def alias_upcontact(self, id):
        return self._get_results('alias-contacts', id=id)
        
    def alias_enable(self, id):
        result = False
        alias = self.get_alias(id)
        if alias and not alias['enabled']:
            self.alias_toggle(id)
            result = True
        return result
            
    def alias_disable(self, id):
        result = False
        alias = self.get_alias(id)
        if alias and alias['enabled']:
            self.alias_toggle(id)
            result = True
        return result
            
    def alias_delete(self, id):
        return self._get_results('alias-delete', id=id)

    def contact_toggle(self, id):
        return self._get_results('contact-toggle', id=id)
        
    def contact_block(self, id):
        result = self.contact_toggle(id)
        if result and 'block_forward' in result and not result['block_forward']:
            self.contact_toggle(id)
            
    def contact_unblock(self, id):
        result = self.contact_toggle(id)
        if result and 'block_forward' in result and result['block_forward']:
            self.contact_toggle(id)
            
    def contact_delete(self, id):
        return self._get_results('contact-delete', id=id)
    
    def call_dynamic(self, name, *args, **kwargs):
        if hasattr(self, name) and callable(func := getattr(self, name)):
            return func(*args, **kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    client = SimpleLogin(apikey=sys.argv[1])
    a = client.get_aliases()
    r = client.get_contacts(a)
    print(json.dumps(r))
