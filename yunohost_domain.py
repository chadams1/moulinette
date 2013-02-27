# -*- coding: utf-8 -*-

import os
import sys
import datetime
import re
from urllib import urlopen
from yunohost import YunoHostError, YunoHostLDAP, win_msg, colorize, validate, get_required_args

def domain_list(filter=None, limit=None, offset=None):
    """
    List YunoHost domains

    Keyword argument:
        filter -- LDAP filter to search with
        limit
        offset

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        result_list = []
        if offset: offset = int(offset)
        else: offset = 0
        if limit: limit = int(limit)
        else: limit = 1000
        if not filter: filter = 'virtualdomain=*'

        result = yldap.search('ou=domains,dc=yunohost,dc=org', filter, attrs=['virtualdomain'])

        if result and len(result) > (0 + offset) and limit > 0:
            i = 0 + offset
            for domain in result[i:]:
                if i <= limit:
                    result_list.append(domain['virtualdomain'][0])
                    i += 1
        else:
            raise YunoHostError(167, _("No domain found"))

        return { 'Domains': result_list }


def domain_add(domains):
    """
    Add one or more domains

    Keyword argument:
        domains -- List of domains to add

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        attr_dict = { 'objectClass' : ['mailDomain', 'top'] }
        ip = str(urlopen('http://ip.yunohost.org').read())
        now = datetime.datetime.now()
        timestamp = str(now.year) + str(now.month) + str(now.day)
        result = []

        if not isinstance(domains, list):
            domains = [ domains ]

        for domain in domains:
            yldap.validate_uniqueness({ 'virtualdomain' : domain })
            attr_dict['virtualdomain'] = domain

            try:
                with open('/var/lib/bind/'+ domain +'.zone') as f: pass
            except IOError as e:
                zone_lines = [
                 '$TTL    38400',
                 domain +'.      IN   SOA   ns.'+ domain +'. root.'+ domain +'. '+ timestamp +' 10800 3600 604800 38400',
                 domain +'.      IN   NS    ns.'+ domain +'.',
                 domain +'.      IN   A     '+ ip,
                 domain +'.      IN   MX    5 mail.'+ domain +'.',
                 domain +'.      IN   TXT   "v=spf1 a mx a:'+ domain +' ?all"',
                 'mail.'+ domain +'. IN   A     '+ ip,
                 'ns.'+ domain +'.   IN   A     '+ ip,
                 'root.'+ domain +'. IN   A     '+ ip
                ]
                with open('/var/lib/bind/' + domain + '.zone', 'w') as zone:
                    for line in zone_lines:
                        zone.write(line + '\n')
            else:
                raise YunoHostError(17, _("Zone file already exists for ") + domain)

            conf_lines = [
                'zone "'+ domain +'" {',
                '    type master;',
                '    file "/var/lib/bind/'+ domain +'.zone";',
                '    allow-transfer {',
                '        127.0.0.1;',
                '        localnets;',
                '    };',
                '};'
            ]
            with open('/etc/bind/named.conf.local', 'a') as conf:
                for line in conf_lines:
                        conf.write(line + '\n')

            if yldap.add('virtualdomain=' + domain + ',ou=domains', attr_dict):
                result.append(domain)
                continue
            else:
                raise YunoHostError(169, _("An error occured during domain creation"))

        win_msg(_("Domain(s) successfully created"))

        return { 'Domains' : result }


def domain_remove(domains):
    """
    Remove domain from LDAP

    Keyword argument:
        domains -- List of domains to remove

    Returns:
        Dict
    """
    with YunoHostLDAP() as yldap:
        result = []

        if not isinstance(domains, list):
            domains = [ domains ]

        for domain in domains:
            if yldap.remove('virtualdomain=' + domain + ',ou=domains'):
                try:
                    os.remove('/var/lib/bind/'+ domain +'.zone')
                except:
                    pass
                with open('/etc/bind/named.conf.local', 'r') as conf:
                    conf_lines = conf.readlines()
                with open('/etc/bind/named.conf.local', 'w') as conf:
                    in_block = False
                    for line in conf_lines:
                        if re.search(r'^zone "'+ domain, line):
                            in_block = True
                        if in_block:
                            if re.search(r'^};$', line):
                                in_block = False
                        else:
                            conf.write(line)
                result.append(domain)
                continue
            else:
                raise YunoHostError(169, _("An error occured during domain deletion"))

        win_msg(_("Domain(s) successfully deleted"))

        return { 'Domains' : result }

