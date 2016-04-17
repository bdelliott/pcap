import collections
import ConfigParser
import datetime
import json
import logging
import os
import re
import time

import selenium.common.exceptions
from selenium import webdriver

CONF_DIR = os.path.expanduser("~/.pcap")
DOMAIN_RE = re.compile(r'https://(?P<domain>.*?)/.*$')

LOG = logging.getLogger(__name__)

Account = collections.namedtuple('Account', ['name', 'detail',
                                             'type', 'balance'])


def read_config():
    cfg = ConfigParser.RawConfigParser()

    path = os.path.join(CONF_DIR, "pcap.conf")
    cfg.read([path])
    return cfg


class PersonalCapital(object):

    def __init__(self):
        self.username, self.password = self._creds()
        self.browser = webdriver.Firefox()
        self.cookies = self._load_cookies()

    def _accounts(self):
        """Make a single attempt to read the account values"""
        accts = []

        sadiv = self.browser.find_element_by_xpath(
            "//div[@id='sidebarAccounts']")

        # get net worth total
        nw = sadiv.find_element_by_xpath(".//div[@class='netWorth']")
        amount = nw.find_element_by_xpath("./div[@class='amount']")
        LOG.debug("Net worth: %s" % amount.text)

        # now do lists of accounts
        alist = sadiv.find_element_by_xpath(".//ul[@class='accountsList']")

        # get bank accounts:
        ul = alist.find_element_by_xpath(
            ".//li[@class='accountGroup BANK']/ul")
        accounts = ul.find_elements_by_xpath(".//li")
        for account in accounts:
            rows = account.find_elements_by_xpath(".//div[@class='row']")
            row = rows[0]
            name = row.find_element_by_xpath("./a").text
            value = row.find_element_by_xpath("./div[@class='balance']").\
                get_attribute('title')

            # 2nd row has the full account name details:
            row = rows[1]
            detail = row.find_element_by_xpath("./div[@class='accountName']")\
                .text

            LOG.debug("Bank account: %s - %s = %s" % (name, detail, value))

            accts.append(
                Account(name, detail, 'cash', self._currency_to_float(value))
            )

        # get investment accounts:
        ul = alist.find_element_by_xpath(
            ".//li[@class='accountGroup INVESTMENT']/ul")
        accounts = ul.find_elements_by_xpath(".//li")
        for account in accounts:
            rows = account.find_elements_by_xpath("./div[@class='row']")

            row = rows[0]
            a = row.find_element_by_xpath("./a")

            # now sure why, but .text was not always working:
            name = a.get_attribute('innerHTML')

            value = row.find_element_by_xpath("./div[@class='balance']").\
                get_attribute('title')

            # 2nd row has the full account name details:
            row = rows[1]
            detail = row.find_element_by_xpath("./div[@class='accountName']")\
                .get_attribute('title')

            LOG.debug("Investment account: %s - %s = %s" % (name, detail,
                                                            value))

            accts.append(
                Account(name, detail, 'investment',
                        self._currency_to_float(value))
            )

        return accts

    def _add_cookies(self):
        """Add any cookies for the current browser page"""

        LOG.debug("Current browser url: %s" % self.browser.current_url)

        m = re.search(DOMAIN_RE, self.browser.current_url)
        domain = m.groupdict()['domain']
        LOG.debug("Adding cookies for domain: %s" % domain)

        for c in self.cookies:
            # if the cookie domain is a substring of the
            # browser domain, add the cookie to the session:
            if domain.find(c['domain']) != -1:
                # LOG.debug("Maybe adding cookie: %s" % c)

                # make sure cookie doesn't already exist
                if self.browser.get_cookie(c['name']):
                    # LOG.debug("Cookie %s already added" % c['name'])
                    continue

                else:
                    LOG.debug("Adding cookie: %s" % c)
                    self.browser.add_cookie(c)

    def _creds(self):
        cfg = read_config()

        username = cfg.get('DEFAULT', 'username')
        password = cfg.get('DEFAULT', 'password')
        return username, password

    def _currency_to_float(self, s):
        """Convert a currency string to a float"""

        # remove leading $ and ,'s
        return float(s.replace('$', '').replace(',', ''))

    def _load_cookies(self):
        """Add saved cookies to the current session"""
        cfile = os.path.join(CONF_DIR, 'cookies.json')

        if not os.path.exists(cfile):
            LOG.debug("No saved cookies")
            return []

        f = open(cfile, 'r')
        buf = f.read()
        cookies = json.loads(buf)
        f.close()

        LOG.debug("Loaded %d saved cookies" % len(cookies))

        # prune out cookies that have expired
        now = datetime.datetime.utcnow()
        cookies2 = []

        for c in cookies:
            e = c['expiry']
            e = datetime.datetime.utcfromtimestamp(e)
            if e < now:
                LOG.debug("Skipping expired cookie: %s (%s)" % (c['name'], e))
                continue

            cookies2.append(c)

        return cookies2

    def _login_container(self):
        return self.browser.find_element_by_xpath(
            "//div[@id='loginContainer']")

    def _save_cookies(self):
        """Save cookies so we can present as a known device for
        subsequent login sessions."""
        cookies = self.browser.get_cookies()
        LOG.debug("Saving %d cookies" % len(cookies))

        # prune cookies without an expiration, meaning
        # they don't last past the current session
        num = len(cookies)
        cookies = [c for c in cookies if c['expiry'] is not None]

        pruned = num - len(cookies)
        LOG.debug("Pruned %d session cookies" % pruned)

        cfile = os.path.join(CONF_DIR, 'cookies.json')
        f = open(cfile, 'w')
        buf = json.dumps(cookies, indent=4, sort_keys=True)
        f.write(buf)
        f.close()

        LOG.debug("Saved %d cookies" % len(cookies))

    def _visible(self, form):
        style = form.get_attribute('style')
        return style == 'display: block;'

    def accounts(self):
        """Scrape account values from dashboard page"""

        # the dom is periodically modified, so try to
        # read all account values in one shot, or
        # start over the dom is modified
        stale = selenium.common.exceptions.StaleElementReferenceException
        for i in range(5):
            try:
                return self._accounts()
            except stale as e:
                LOG.error("DOM modification during account read: %s.  Will "
                          "retry" % e)

        raise Exception("Repeated failure to read account list.  Giving up.")

    def login(self):
        # load home page
        browser = self.browser
        browser.get('https://www.personalcapital.com/')
        self._add_cookies()

        # load sign-in page
        browser.get('https://home.personalcapital.com/page/login/goHome')
        self._add_cookies()

        # fill out email form
        form = browser.find_element_by_xpath("//form[@id='form-email']")
        input_elt = form.find_element_by_xpath(".//input[@name='username']")
        input_elt.send_keys(self.username)
        submit = form.find_element_by_xpath(".//button[@type='submit']")
        submit.click()

        # stays on same page, but styling shifts -- when the email form gets
        # hidden, it's safe to continue
        while self._visible(form):
            time.sleep(0.1)

        # now from here we will either hit a page with a password prompt if the
        # device is approved, or we need to approve the device with human
        # intervention
        container = self._login_container()
        form = container.find_element_by_xpath(
            "./form[@id='form-challengeRequest']")

        if self._visible(form):
            # challenge form *is* displayed -- click continue button, challenge
            # will be sent to an authorized device
            LOG.debug("Handling challenge form")
            button = form.find_element_by_xpath(".//button[@type='submit']")
            button.click()

            LOG.debug("Waiting here for human to complete challenge!")

        # loop until the password form becomes visible
        while True:
            LOG.debug("Waiting for password prompt")
            container = self._login_container()
            form = container.find_element_by_xpath(
                "./form[@id='form-password']")

            if not self._visible(form):
                LOG.debug("Password prompt not yet ready")
                time.sleep(1.0)
            else:
                break

        LOG.debug("Moving on to password entry")
        container = self._login_container()
        form = container.find_element_by_xpath("./form[@id='form-password']")
        field = form.find_element_by_xpath(".//input[@type='password']")
        field.send_keys(self.password)

        button = form.find_element_by_xpath(".//button[@type='submit']")
        button.click()

        LOG.debug("Waiting for page change to dashboard")
        while True:
            if browser.title == 'Personal Capital - Dashboard':
                break

            time.sleep(0.1)

        LOG.debug("Now on pcap dashboard page!")

        # save cookies now that we're logged in
        self._save_cookies()


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger('selenium').setLevel(logging.INFO)

    pcap = PersonalCapital()
    pcap.login()
    accounts = pcap.accounts()

    LOG.debug("Account values: %s" % accounts)
