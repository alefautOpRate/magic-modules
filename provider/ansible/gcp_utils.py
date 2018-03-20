# Copyright (c), Google Inc, 2017
# Simplified BSD License (see licenses/simplified_bsd.txt or https://opensource.org/licenses/BSD-2-Clause)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import google.auth
    import google.auth.compute_engine
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    HAS_GOOGLE_LIBRARIES = True
except ImportError:
    HAS_GOOGLE_LIBRARIES = False

from ansible.module_utils.basic import AnsibleModule, env_fallback
from ansible.module_utils.six import string_types
import os


def navigate_hash(source, path, default=None):
    key = path[0]
    path = path[1:]
    if key not in source:
        return default
    result = source[key]
    if path:
        return navigate_hash(result, path, default)
    else:
        return result


# Handles all authentation and HTTP sessions for GCP API calls.
class GcpSession(object):
    def __init__(self, module, product):
        self.module = module
        self.product = product
        self._validate()

    def get(self, url, body=None):
        try:
            return self.session().get(url, json=body, headers=self._headers())
        except getattr(requests.exceptions, 'RequestException') as inst:
            raise GcpRequestException(inst.message)

    def post(self, url, body=None):
        try:
            return self.session().post(url, json=body, headers=self._headers())
        except getattr(requests.exceptions, 'RequestException') as inst:
            raise GcpRequestException(inst.message)

    def delete(self, url, body=None):
        try:
            return self.session().delete(url, json=body, headers=self._headers())
        except getattr(requests.exceptions, 'RequestException') as inst:
            raise GcpRequestException(inst.message)

    def put(self, url, body=None):
        try:
            return self.session().put(url, json=body, headers=self._headers())
        except getattr(requests.exceptions, 'RequestException') as inst:
            raise GcpRequestException(inst.message)

    def session(self):
        return AuthorizedSession(
            self._credentials().with_scopes(self.module.params['scopes']))

    def _validate(self):
        if not HAS_REQUESTS:
            self.module.fail_json(msg="Please install the requests library")

        if not HAS_GOOGLE_LIBRARIES:
            self.module.fail_json(msg="Please install the google-auth library")

        if self.module.params['service_account_email'] is not None and self.module.params['auth_kind'] != 'machineaccount':
            self.module.fail_json(
                msg="Service Acccount Email only works with Machine Account-based authentication"
            )

        if self.module.params['service_account_file'] is not None and self.module.params['auth_kind'] != 'serviceaccount':
            self.module.fail_json(
                msg="Service Acccount File only works with Service Account-based authentication"
            )

    def _credentials(self):
        cred_type = self.module.params['auth_kind']
        if cred_type == 'application':
            credentials, project_id = google.auth.default()
            return credentials
        elif cred_type == 'serviceaccount':
            return service_account.Credentials.from_service_account_file(
                self.module.params['service_account_file'])
        elif cred_type == 'machineaccount':
            return google.auth.compute_engine.Credentials(
                self.module.params['service_account_email'])
        else:
            self.module.fail_json(msg="Credential type '%s' not implmented" % cred_type)

    def _headers(self):
        return {
            'User-Agent': "Google-Ansible-MM-{0}".format(self.product)
        }


class GcpModule(AnsibleModule):
    def __init__(self, *args, **kwargs):
        arg_spec = {}
        if 'argument_spec' in kwargs:
            arg_spec = kwargs['argument_spec']

        kwargs['argument_spec'] = self._merge_dictionaries(
            arg_spec,
            dict(
                project=dict(required=True, type='str'),
                auth_kind=dict(
                    required=False,
                    fallback=(env_fallback, ['GCP_AUTH_KIND']),
                    choices=['machineaccount', 'serviceaccount', 'application'],
                    type='str'),
                service_account_email=dict(
                    required=False,
                    fallback=(env_fallback, ['GCP_SERVICE_ACCOUNT_EMAIL']),
                    type='str'),
                service_account_file=dict(
                    required=False,
                    fallback=(env_fallback, ['GCP_SERVICE_ACCOUNT_FILE']),
                    type='path'),
                scopes=dict(
                    required=False,
                    fallback=(env_fallback, ['GCP_SCOPES']),
                    type='list')
            )
        )

        mutual = []
        if 'mutually_exclusive' in kwargs:
            mutual = kwargs['mutually_exclusive']

        kwargs['mutually_exclusive'] = mutual.append(
            ['service_account_email', 'service_account_file']
        )

        AnsibleModule.__init__(self, *args, **kwargs)

<%
# set_value_for_resource and set_value_with_callback was responsible for
# traversing user input and altering its results.
#
# set_value_for_resource is used for ResourceRefs. It will convert all
# ResourceRefs at `path` from dictionaries (`register: output` from Ansible)
# and grab the output value at `value`
#
# set_value_with_callback will use a auto-generated callback to verify and
# alter values at `path`. This is almost exclusively used to convert
# user-inputted names to self-links
-%>
    # Some params are references to other pieces of GCP infrastructure.
    # These params are passed in as dictionaries.
    # The dictionaries should be overriden with the proper value.
    # The proper value is located at key: 'value' of the dictionary
    def set_value_for_resource(self, path, value, params=None):
        if params is None:
            params = self.params
        try:
            if len(path) == 1:
                # Override dictionary with value from the dictionary
                params[path[0]] = params[path[0]].get(value)
            else:
                params = params[path[0]]
                if isinstance(params, list):
                    for item in params:
                        self.set_value_for_resource(path[1:], value, item)
                else:
                    self.set_value_for_resource(path[1:], value, params)
        except KeyError:
            # Many resources are optional and won't be included.
            # These errors are expected and should be ignored.
            pass
        except AttributeError:
            # Many resources are optional and won't be included.
            # These errors are expected and should be ignored.
            pass

    # Some params are self-links, but many users will enter them as names.
    # These params are passed in as strings
    # These params should be checked and converted to self-links if they
    # are entered as names
    # This function is given a path of values that are expected to be
    # self-links.
    # This function takes in a callbacks to functions that will check + alter
    # names to self_links depending on the resource_type.
    def set_value_with_callback(self, path, callback, params=None):
        if params is None:
            params = self.params
        try:
            if len(path) == 1:
                # Override dictionary with value from the dictionary
                params[path[0]] = callback(params[path[0]], params)
            else:
                params = params[path[0]]
                if isinstance(params, list):
                    for item in params:
                        self.set_value_with_callback(path[1:], callback)
                else:
                    self.set_value_with_callback(path[1:], callback, params)
        except KeyError:
            # Many resources are optional and won't be included.
            # These errors are expected and should be ignored.
            pass
        except AttributeError:
            # Many resources are optional and won't be included.
            # These errors are expected and should be ignored.
            pass

    def raise_for_status(self, response):
        try:
            response.raise_for_status()
        except getattr(requests.exceptions, 'RequestException') as inst:
            self.fail_json(msg="GCP returned error: %s" % response.json())

    def _merge_dictionaries(self, a, b):
        new = a.copy()
        new.update(b)
        return new
