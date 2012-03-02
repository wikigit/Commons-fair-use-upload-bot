#!/usr/bin/python
import mwclient
import ConfigParser
import re
import sys
import time
import urllib

def myprint(str):
    # When stdout is redirected to a log file, we have to choose an encoding.
    print(str.encode('utf-8', 'strict'))

def allow_bots(text, user):
    if (re.search(r'\{\{(nobots|bots\|(allow=none|deny=.*?' + user + r'.*?|optout=all|deny=all))\}\}', text)):
        return False
    return True

def is_commons_admin(user):
    # No API to determine if a user is an administrator, use urllib
    params = urllib.urlencode({'title': 'Special:ListUsers', 'limit': 1, 'username': user.encode("utf-8")})
    opener = MyURLopener()
    f = opener.open("http://commons.wikimedia.org/w/index.php?%s" % params)
    return re.search('<a href="/wiki/Commons:Administrators" title="Commons:Administrators">administrator</a>', f.read())

def download_to_file(page, filename):
    fr = page.download()
    fw = open(filename, 'wb')
    while True:
        s = fr.read(4096)
        if not s: break
        fw.write(s)
    fr.close()
    fw.close()

def format_time(time):
    return '%d-%02d-%02d %02d:%02d:%02d UTC' % \
           (time.tm_year, time.tm_mon, time.tm_mday, time.tm_hour, time.tm_min, time.tm_sec)

def contains_template(template_name, text):
    # Use IGNORECASE to catch redirects with alternate capitalizations
    # TODO: Catch all redirects accurately
    return re.search(r'{{' + template_name + r'[^}]*}}\s*', text, re.IGNORECASE)

def remove_template(template_name, text):
    # Use IGNORECASE to catch redirects with alternate capitalizations
    # TODO: Catch all redirects accurately
    return re.sub(r'(?i){{' + template_name + r'[^}]*}}\s*', '', text, re.IGNORECASE)

# Gets argument of a one-argument template (with default argument name 1)
def get_template_arg(template_name, text):
    # Use IGNORECASE to catch redirects with alternate capitalizations
    # TODO: Catch all redirects accurately
    # TODO: Generalize to retrieving dictionary of all template arguments
    m = re.search(r'{{' + template_name + r'\|(1=)?([^}]*)}}', text, re.IGNORECASE)
    if m:
        return m.group(2)
    else:
        return None

def describe_file_history(sitename, filepage):
    # TODO: localize this based on sitename
    desc = "\n\n== Wikimedia Commons file description page history ==\n"
    for revision in filepage.revisions(prop = 'timestamp|user|comment|content'):
        desc += "* " + format_time(revision['timestamp']) + " [[:commons:User:" + revision['user'] + "|" + revision['user'] + "]] ''<nowiki>" + revision['comment'] + "</nowiki>''\n"
    return desc

def describe_upload_log(sitename, filepage):
    # TODO: localize this based on sitename
    desc = "\n== Wikimedia Commons upload log ==\n"
    for imagehistoryentry in filepage.imagehistory():
        desc += "* " + format_time(imagehistoryentry['timestamp']) + " [[:commons:User:" + imagehistoryentry['user'] + "|" + imagehistoryentry['user'] + "]] " + str(imagehistoryentry['width']) + "&times;" + str(imagehistoryentry['height']) + " (" + str(imagehistoryentry['size']) + " bytes) ''<nowiki>" + imagehistoryentry['comment'] + "</nowiki>''\n"
    return desc

def get_user_who_added_template(template, filepage):
    taguser = "?"
    for revision in filepage.revisions(prop = 'timestamp|user|comment|content'):
        if taguser == '?' and not re.search(r'{{' + template + r'[^}]*}}\s*', revision['*'], re.IGNORECASE):
            taguser = prevuser
        prevuser = revision['user']
    return taguser

def get_request_fair_use_template(reason):
    reason_arg = "|reason=" + reason if reason else ''
    return '{{Request fair use delete' + reason_arg + "}}\n\n"

def get_candidate_template(sitename, reason):
    reason_arg = "|reason=" + reason if reason else ''
    lang = str.split(sitename, '.')[0]
    if lang == 'en':
        return "{{Fair use candidate from Commons|" + filepage.name + reason_arg + "}}\n\n"
    elif lang == 'et':
        return "{{Mittevaba_pildi_kandidaat_Commonsist|" + filepage.name + reason_arg + "}}\n\n"

def get_local_tags(sitename, historyinfo):
    desc = ''
    if (sitename == 'en.wikipedia.org'):
        desc += "{{di-no fair use rationale|date=" + time.strftime("%d %B %Y", time.gmtime()) + "}}\n"
        if historyinfo['width'] > 400:
            desc += "{{Non-free reduce}}\n"
    return desc

def get_notification(sitename, filepage):
    lang = str.split(sitename, '.')[0]
    if lang == 'en':
        return '{{subst:Fair use candidate from Commons notice|' + filepage.name + '}} ~~~~'
    elif lang == 'et':
        return '{{subst:Kasutusel_mittevaba_pildi_kandidaat|' + filepage.name + '}} ~~~~'

def get_notification_summary(sitename, filepage):
    lang = str.split(sitename, '.')[0]
    # TODO: localize
    return 'Bot notice: Fair use candidate from Commons: ' + filepage.name

def get_install_redirect_summary(sitename):
    # TODO: localize
    return 'Bot creating image redirect to local re-upload of image being deleted at Commons'

def append_to_filename(suffix, filename):
    return re.sub(r'^File:(.*)\.([^.]*)$', r'\1' + suffix + r'.\2', filepage.name)

class MyURLopener(urllib.FancyURLopener):
    version = 'Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US; rv:1.9.2.4) Gecko/20100527 Firefox/3.6.4'

myprint('Starting Commons fair use upload bot run at ' + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
sys.stdout.flush()

supported_wikis = ['et.wikipedia.org', 'en.wikipedia.org', 'en.wikibooks.org']
pd_us_wikis = ['en.wikipedia.org', 'en.wikisource.org', 'wikisource.org']

sitecommons = mwclient.Site('commons.wikimedia.org')
config = ConfigParser.RawConfigParser()
config.read('Commons_fair_use_upload_bot.credentials.txt')
username = config.get('mwclient', 'username')
password = config.get('mwclient', 'password')
sitecommons.login(username, password)

dry_run = False
# dry_run = True

category = sitecommons.Pages['Category:Pending fair use deletes']
for filepage in category:
    if filepage.namespace != 6:
        continue
    myprint(filepage.name)
    sys.stdout.flush()
    download_to_file(filepage, '/tmp/downloadedfile')
    filedescription = filepage.edit()
    if not contains_template('Fair use delete', filedescription):
        myprint('No Fair use delete tag found for ' + filepage.name)
        continue
    reason = get_template_arg('Fair use delete', filedescription)
    filedescription = remove_template('Fair use delete', filedescription)

    taguser = get_user_who_added_template('Fair use delete', filepage)
    if not is_commons_admin(taguser):
        myprint('Request was made by non-admin user "' + taguser.encode('ascii', 'ignore') + '" for ' + filepage.name + ', replacing with {{Request fair use delete}}')
        filedescription = get_request_fair_use_template(reason) + filedescription
        if not dry_run:
            filepage.save(filedescription, summary = '{{tl|Fair use delete}} tag must be placed by an admin, changing to {{tl|Request fair use delete}}')
        else:
            myprint("New file description:\n" + filedescription)
        continue
    myprint('Tag added by administrator ' + taguser)

    historyinfo = filepage.imagehistory().next()

    #site = mwclient.Site('et.wikipedia.org')
    #site.login(username, password)
    #filepagelocal = site.Images[filepage.page_title]
    #if len(list(filepagelocal.imageusage())) > 0:
        #myprint('Skipping (User:Commons fair use upload bot]] does not yet have upload privileges on etwiki)')
        #continue

    uploaded_sites = []
    for sitename in supported_wikis:
        site = mwclient.Site(sitename)
        site.login(username, password)

        filepagelocal = site.Images[filepage.page_title]
        if len(list(filepagelocal.imageusage())) == 0:
            continue

        uploaded_sites.append(sitename)
        newdesc = get_local_tags(sitename, historyinfo) + \
                  get_candidate_template(sitename, reason) + \
                  filedescription + \
                  describe_file_history(sitename, filepage) + \
                  describe_upload_log(sitename, filepage) + \
                  "__NOTOC__\n"
        newfilename = append_to_filename(' - from Commons', filepage.name)
        myprint('Uploading /tmp/downloadedfile to ' + newfilename)
        sys.stdout.flush()
        if not dry_run:
            site.upload(open('/tmp/downloadedfile'), newfilename, newdesc, ignore=True)
        # We upload at a new name and redirect to get around permission limitations on some (all?) wikis
        # which prevent uploading over files still present at Commons.
        if not dry_run:
            filepagelocal.save('#REDIRECT[[File:' + newfilename + ']]', summary = get_install_redirect_summary(sitename))

        for page in filepagelocal.imageusage(namespace=0):
            myprint('In use on page ' + page.name + ' on ' + sitename)
            talkpage = site.Pages['Talk:' + page.name]
            text = talkpage.edit()
            if allow_bots(text, 'Commons fair use upload bot'):
                myprint('Updating talk page ' + talkpage.name + ' with notice')
                sys.stdout.flush()
                if not dry_run:
                    talkpage.save(text + "\n" + get_notification(sitename, filepage), summary = get_notification_summary(sitename, filepage))
                else:
                    myprint("Notification:\n" + get_notification(sitename, filepage))
                    myprint("Edit summary: " + get_notification_summary(sitename, filepage))

    myprint('Marking file for speedy deletion...')
    sys.stdout.flush()
    speedyreason = reason if reason else 'Marked for deletion.'
    if not re.search(r'\.$', speedyreason):
        speedyreason += '.'
    if len(uploaded_sites) > 0:
        speedyreason += " Copies uploaded to " + str.join(', ', uploaded_sites) + " as fair use candidates."
    filedescription = "{{speedydelete|" + speedyreason + "}}\n\n" + filedescription
    if not dry_run:
        filepage.save(filedescription, summary = 'Finished uploading fair use image to local projects, marking for speedy deletion')
    else:
        myprint("New file page:\n" + filedescription)
    myprint('Done.')

myprint('Run completed at ' + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
exit()

category = sitecommons.Pages['Category:Images in the public domain in the United States but not the source country']
for filepage in category:
    print filepage.name
    download_to_file(filepage, '/tmp/downloadedfile')
    filedescription = filepage.edit()
    if not re.search(r'{{PD-US-1923-abroad-delete}}', filedescription, re.IGNORECASE):
        print 'No {{PD-US-1923-abroad-delete}} tag found for ' + filepage.name
        continue
    m = re.search(r'{{PD-US-1923-abroad-delete}}', filedescription, re.IGNORECASE)
    filedescription = re.sub(r'(?i){{PD-US-1923-abroad-delete}}\s*', '', filedescription)
    filedescription = re.sub(r'(?i){{PD-US}}\s*', '', filedescription)
    filedescription = re.sub(r'(?i){{PD-1923}}\s*', '', filedescription)
    filedescription = re.sub(r'(?i){{PD-US-1923}}\s*', '', filedescription)
    filedescription = re.sub(r'(?i){{PD-pre-1923}}\s*', '', filedescription)
    filedescription = re.sub(r'(?i){{PD-pre1923}}\s*', '', filedescription)

    newdesc = "{{PD-US-1923-abroad}}\n\n" + filedescription
    # TODO: localize this
    newdesc += "\n\n== Wikimedia Commons file description page history ==\n"
    taguser = "?"
    for revision in filepage.revisions(prop = 'timestamp|user|comment|content'):
        if taguser == '?' and not re.search(r'{{PD-US-1923-abroad-delete}}\s*', revision['*'], re.IGNORECASE):
            taguser = prevuser
        newdesc += "* " + format_time(revision['timestamp']) + " [[:commons:User:" + revision['user'] + "|" + revision['user'] + "]] ''<nowiki>" + revision['comment'] + "</nowiki>''\n"
        prevuser = revision['user']

    # No API to determine if a user is an administrator, use urllib
    if not is_commons_admin(taguser):
        print 'Request was made by non-admin user "' + taguser + '" for ' + filepage.name
        continue
    print 'Tag added by administrator ' + taguser

    # TODO: localize this
    newdesc += "\n== Wikimedia Commons upload log ==\n"
    width = -1
    height = -1
    for imagehistoryentry in filepage.imagehistory():
        if width == -1:
            width = imagehistoryentry['width']
            height = imagehistoryentry['height']
        # TODO: localize this
        newdesc += "* " + format_time(imagehistoryentry['timestamp']) + " [[:commons:User:" + imagehistoryentry['user'] + "|" + imagehistoryentry['user'] + "]] " + str(imagehistoryentry['width']) + "&times;" + str(imagehistoryentry['height']) + " (" + str(imagehistoryentry['size']) + " bytes) ''<nowiki>" + imagehistoryentry['comment'] + "</nowiki>''\n"
    newdesc += "__NOTOC__\n"

    uploaded_sites = ''
    for sitename in pd_us_wikis:
        site = mwclient.Site(sitename)
        site.login(username, password)

        filepagelocal = site.Pages[filepage.name]

        if uploaded_sites:
            uploaded_sites += ', '
        uploaded_sites += sitename

        newfilename = re.sub(r'^File:(.*)\.([^.]*)$', r'\1 - from Commons.\2', filepage.name)
        print 'Uploading /tmp/downloadedfile to ' + newfilename
        newdesclocal = newdesc
        site.upload(open('/tmp/downloadedfile'), newfilename, newdesclocal, ignore=True)
        # We upload at a new name and redirect to get around permission limitations on some wikis
        # which prevent uploading over files still present at Commons.
        filepagelocal.save('#REDIRECT[[File:' + newfilename + ']]', summary = 'Bot creating image redirect to local re-upload of image being deleted at Commons')

    print 'Marking file for speedy deletion...'
    if uploaded_sites:
        reason = "Copies uploaded to " + uploaded_sites + " as public domain in the United States only."
    filedescription = "{{speedydelete|" + reason + "}}\n\n" + filedescription
    filepage.save(filedescription, summary = 'Finished uploading as public domain in the United States only to local projects, marking for speedy deletion')
    print 'Done.'
