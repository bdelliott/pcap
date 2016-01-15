import logging
import time

from selenium import webdriver

LOG = logging.getLogger(__name__)


def _login_container(browser):
    return browser.find_element_by_xpath("//div[@id='loginContainer']")

def _visible(form):
    style = form.get_attribute('style')
    return style == 'display: block;'


def do_login(browser):
    # load home page
    browser.get('https://www.personalcapital.com/')

    # load sign-in page
    browser.get('https://home.personalcapital.com/page/login/goHome')

    # fill out email form
    form = browser.find_element_by_xpath("//form[@id='form-email']")
    input_elt = form.find_element_by_xpath(".//input[@name='username']")
    input_elt.send_keys('bdelliott@gmail.com')
    submit = form.find_element_by_xpath(".//button[@type='submit']")
    submit.click()

    # stays on same page, but styling shifts -- when the email form gets
    # hidden, it's safe to continue
    while _visible(form):
        time.sleep(0.1)

    # now from here we will either hit a page with a password prompt if the
    # device is approved, or we need to approve the device with human intervention
    container = _login_container(browser)
    form = container.find_element_by_xpath("./form[@id='form-challengeRequest']")

    if _visible(form):
        # challenge form *is* displayed -- click continue button, challenge will be
        # sent to an authorized device
        LOG.debug("Handling challenge form")
        button = form.find_element_by_xpath(".//button[@type='submit']")
        button.click()        

        LOG.debug("Waiting here for human to complete challenge!")

    # loop until the password form becomes visible
    while True:
        LOG.debug("Waiting for password prompt")
        container = _login_container(browser)
        form = container.find_element_by_xpath("./form[@id='form-password']")
        if not _visible(form):
            LOG.debug("Password prompt not yet ready")
            time.sleep(1.0)
        else:
            break

    LOG.debug("Moving on to password entry")
    import pdb; pdb.set_trace()


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger('selenium').setLevel(logging.INFO)

    browser = webdriver.Firefox()
    do_login(browser)
